# Key bindings stuff
# See http://zsh.sourceforge.net/Doc/Release/Zsh-Line-Editor.html

bindkey -v # Use vi key bindings

# [Esc-.] - run command: .. (up directory)
bindkey -s '\e.' '..\n'

# [Ctrl-r] - Search backward incrementally for a specified string.
# The string may begin with ^ to anchor to the beginning of the line.
bindkey '^r' history-incremental-search-backward    

# Some emacs style stuff
bindkey '^a' beginning-of-line
bindkey '^e' end-of-line
