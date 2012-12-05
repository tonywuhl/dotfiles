#!/usr/bin/env bash
export GIT_THEME_PROMPT_PREFIX=" ("
export GIT_THEME_PROMPT_SUFFIX=")"

function prompt_command() {
PS1="${yellow}\h${reset_color}:${cyan}\W${reset_color}${green}$(scm_prompt_info)${purple} >>${reset_color} ";
}

PROMPT_COMMAND=prompt_command;
