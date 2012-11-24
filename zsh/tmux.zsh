# Configure tmux to use the right configuration file
if [[ "$(uname)" = "Darwin" ]]; then
    alias tmux='tmux -2 -f $HOME/.tmux-osx.conf'
else
    alias tmux='tmux -2'
fi
