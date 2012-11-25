" Customization
" Loads post-configuration settings

if !has("gui_running")
  if &t_Co >= 256
    let g:solarized_termtrans = 1
	set background=dark
    colorscheme solarized
  endif
endif

if filereadable(expand("~/.vimrc.after"))
  source ~/.vimrc.after
endif
