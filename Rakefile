require 'rake'

DOTFILESDIR = Rake.application.original_dir

desc "Hook our dotfiles into system-standard positions."
task :install => [:submodule_init, :submodules] do
  # Install Mac-related stuff
  if RUBY_PLATFORM.downcase.include?("darwin")
    install_homebrew
    install_fonts
  end
  linkables = Dir.glob('*/**{.symlink}')

  skip_all = false
  overwrite_all = false
  backup_all = false

  linkables.each do |linkable|
    overwrite = false
    backup = false

    file = linkable.split('/').last.split('.symlink').last
    target = "#{ENV["HOME"]}/.#{file}"

    if File.exists?(target) || File.symlink?(target)
      unless skip_all || overwrite_all || backup_all
        puts "File already exists: #{target}, what do you want to do? [s]kip, [S]kip all, [o]verwrite, [O]verwrite all, [b]ackup, [B]ackup all"
        case STDIN.gets.chomp
        when 'o' then overwrite = true
        when 'b' then backup = true
        when 'O' then overwrite_all = true
        when 'B' then backup_all = true
        when 'S' then skip_all = true
        when 's' then next
        end
      end
      FileUtils.rm_rf(target) if overwrite || overwrite_all
      run %{mv "$HOME/.#{file}" "$HOME/.#{file}.backup"} if backup || backup_all
    end
    run %{ln -s "$PWD/#{linkable}" "#{target}"}
  end

  puts "Creating directories for ZSH customizations"
  run %{ mkdir -p $HOME/.zsh.before }
  run %{ mkdir -p $HOME/.zsh.after }
  run %{ mkdir -p $HOME/.zsh.prompts }

  unless File.exists?(File.join(ENV['ZDOTDIR'] || ENV['HOME'], ".zprezto"))
    run %{ ln -nfs "$HOME/.yadr/zsh/prezto" "${ZDOTDIR:-$HOME}/.zprezto" }
  end

  puts "Installed all dotfiles."
end

task :submodule_init do
  unless ENV["SKIP_SUBMODULES"]
    run %{git submodule update --init --recursive}
  end
end

desc "Init and update submodules."
task :submodules do
  unless ENV["SKIP_SUBMODULES"]
    puts "Downloading submodules"

    run %{
      cd "#{DOTFILESDIR}"
      git submodule foreach 'git fetch origin; git checkout master; git reset --hard origin/master; git submodule update --recursive; git clean -dfx'
      git clean -dfx
    }
    puts
  end
end

task :default => 'install'

private

def run(cmd)
  puts "[Running] #{cmd}"
  `#{cmd}` unless ENV['DEBUG']
end

def install_homebrew
  puts "Installing homebrew"
  run %{ruby -e "$(curl -fsSkL raw.github.com/mxcl/homebrew/go)"}
  puts "Installing homebrew packages"
  run %{brew install ack ctags git hub bash zsh tmux reattach-to-user-namespace}
  puts "Enter \"yes\" when you finish reading the caveats from the homebrew command"
  begin
    ans = STDIN.gets.chomp
  end while !(ans == "y" || ans == "yes")
end

def install_fonts
  puts "Installing patched fonts for Powerline."
  run %{cp -f $DOTFILESDIR/fonts/* $HOME/Library/Fonts}
end

