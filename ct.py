import argparse
import configparser
import curses
import io
import json
import os
import sys
import time
import re
import shutil
import zipfile

from pathlib import Path

import requests

session = requests.Session()
session.headers.update({"User-Agent": "ContestTools"})

CONFIG_PATH = Path.home() / ".contestrc"
config = configparser.ConfigParser()
if not config.read(CONFIG_PATH):
    raise Exception("Invalid or missing ~/.contestrc file")


class Language:
    def __init__(self, extensions, name):
        self.extensions = extensions
        self.name = name

    def is_lang(self, path):
        if path.split(".")[-1] in self.extensions:
            return True
        return False

LANGUAGES = {
    "cpp": Language(extensions=["cpp", "h"], name="C++"),
    "py": Language(extensions=["py"], name="Python 3"),
}

def find_language(path):
    for lang_id, lang in LANGUAGES.items():
        if lang.is_lang(path):
            return lang_id, lang
    raise Exception(f"No language for {path}")


def login():
    username = config.get("user", "username")
    token = config.get("user", "token")
    url = config.get("kattis", "loginurl")

    args = {
        "user": username,
        "script": "true",
        "token": token
    }
    session.post(url, data=args)

def submit():
    cwd = Path.cwd()
    problem = cwd.name
    files = []
    for p in cwd.iterdir():
        if p.name.startswith("solution."):
            _, language = find_language(p.name)
            with p.open() as f:
                files.append(
                    ("sub_file[]", (p.name, f.read(), "application/octet-stream")))
    if not files:
        raise Exception("No solution.* files!")


    data = {"submit": "true",
            "submit_ctr": 2,
            "language": language.name,
            "problem": problem,
            "script": "true"}
    url = config.get("kattis", "submissionurl")
    response = session.post(url, data=data, files=files)
    text = response.text.replace("<br/>", "\n")
    if response.status_code != 200:
        print(text)
        return None
    if "token" in text:
        print(text)
        return None
    return re.search(r"\d+", text).group()

STATUSES = {
  0: "New",
  1: "New",
  2: "New",
  3: "Compiling",
  4: "Running",
  5: "Running",
  8: "Compile Error",
  9: "Run-Time Error",
  10: "Memory Limit Exceeded",
  11: "Output Limit Exceeded",
  12: "Time Limit Exceeded",
  14: "Wrong Answer",
  16: "Accepted",
}


def watch(submission_id):
    print(f"Submitted as ID {submission_id}")
    url = f"{config.get('kattis', 'submissionsurl')}/{submission_id}?json"

    submission_status = "New"

    def poller(stdscr):
        nonlocal submission_status
        curses.noecho()

        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLACK)

        while True:
            text = session.get(url).text
            data = json.loads(text)

            submission_status_id = data["status_id"]
            submission_status = STATUSES[submission_status_id]
            tc_statuses = re.findall(r"Test case \d+/\d+: (.*?)\"", data["row_html"])

            stdscr.clear()
            rows, cols = stdscr.getmaxyx()
            stdscr.addstr(0, 0, "Status: ")
            if submission_status == "Accepted":
                stdscr.addstr(0, 8, f"{submission_status} \u2714", curses.color_pair(1))
            elif submission_status_id >= 9:
                stdscr.addstr(0, 8, f"{submission_status} \u2718", curses.color_pair(2))
            elif tc_statuses:
                for tc, tc_status in enumerate(tc_statuses):
                    if tc_status == "not checked":
                        stdscr.addstr(0, 8, f"{tc + 1}/{len(tc_statuses)}")
                        break
                else:
                    stdscr.addstr(0, 8, f"...")
            else:
                stdscr.addstr(0, 8, f"{submission_status}")

            for tc, tc_status in enumerate(tc_statuses):
                r = 1
                c = tc * 2
                r += c // cols
                c %= cols
                if c % 2: c -= 1
                if tc_status == "not checked":
                    stdscr.addstr(r, c, f"\u2610")
                elif tc_status == "Accepted":
                    stdscr.addstr(r, c, f"\u2714", curses.color_pair(1))
                else:
                    stdscr.addstr(r, c, f"\u2718", curses.color_pair(2))

            stdscr.refresh()

            if submission_status_id >= 8:
                time.sleep(4)
                break
            time.sleep(0.3)
    curses.wrapper(poller)
    print(f"Status: {submission_status}")


def submit_command(args):
    submission_id = submit()
    if submission_id:
        login()
        watch(submission_id)

def new_command(args):
    host = f"https://{config.get('kattis', 'hostname')}"
    sample_path = f"{host}/problems/{args.problem}/file/statement/samples.zip"
    r = session.get(sample_path, stream=True)
    if r.status_code != 200:
        raise Exception("Failed getting samples")

    problem_path = Path.cwd() / args.problem
    try:
        problem_path.mkdir()
    except FileExistsError:
        pass
    os.chdir(problem_path)
    sample_zip = zipfile.ZipFile(io.BytesIO(r.content))
    sample_zip.extractall("tests")

    lang = args.language
    template_path = config.get("template", lang)
    shutil.copy(template_path, f"solution.{lang}")

    print(problem_path)

def test_command(args):
    path_dir = Path.cwd()
    problem = path_dir.name
    for p in path_dir.iterdir():
        if p.name.startswith("solution."):
            lang_id, _ = find_language(p.name)
            break
    else:
        print("No solution file??")
    if lang_id in config['compile']:
        if os.system(config.get('compile', lang_id).replace("{files}", str(p))):
            return
    run_cmd = config.get('run', lang_id).replace("{files}", str(p)) + "<tests/{} | diff - tests/{}"
    for x in os.listdir("tests"):
        if x.endswith('.in'):
            os.system(run_cmd.format(x, x[:-3] + ".ans"))

def main():
    login()

    parser = argparse.ArgumentParser(prog="ct")
    subparsers = parser.add_subparsers()

    submit_parser = subparsers.add_parser("submit")
    submit_parser.set_defaults(func=submit_command)

    new_parser = subparsers.add_parser("new")
    new_parser.add_argument("problem")
    new_parser.add_argument("--language", '-l', default="cpp")
    new_parser.set_defaults(func=new_command)

    submit_parser = subparsers.add_parser("test")
    submit_parser.set_defaults(func=test_command)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
