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
      if skip_all
        next
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

task :uninstall do
  Dir.glob('**/*.symlink').each do |linkable|

    file = linkable.split('/').last.split('.symlink').last
    target = "#{ENV["HOME"]}/.#{file}"

    # Remove all symlinks created during installation
    if File.symlink?(target)
      FileUtils.rm(target)
    end
    
    # Replace any backups made during installation
    if File.exists?("#{ENV["HOME"]}/.#{file}.backup")
      `mv "$HOME/.#{file}.backup" "$HOME/.#{file}"` 
    end

  end
  puts "Uninstalled all dotfiles."
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
end

def install_fonts
  puts "Installing patched fonts for Powerline."
  run %{cp -f $DOTFILESDIR/fonts/* $HOME/Library/Fonts}
end

