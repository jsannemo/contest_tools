alias c='g++ -Wall -std=gnu++11 -g -Wconversion -ftrapv -Wfatal-errors -fsanitize=undefined -D_GLIBCXX_DEBUG'
new() {
	cd `_new $1 $2` 
	vim $1.*
}
