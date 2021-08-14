from utils.file import delete_dir, get_file_list
from utils.logger import log
from .config import Config
from hashlib import md5
from pathlib import Path
import shlex
import subprocess as sp


class Builder(Config):
    # ========================================= #
    # Main builder class                        #
    # performs specific actions based           #
    # on command-line arguments                 #
    # ========================================= #
    def __init__(self, path: Path):
        super().__init__(path)

    # Create target and build directories           #
    # --------------------------------------------- #
    def prepare_build_dirs(self):
        log.info('Checking if build and target dirs are present...')

        if not self.dirs['build'].exists():
            self.dirs['build'].mkdir()

        for path in self.dirs['target']:
            if not path.exists():
                path.mkdir(parents=True)

    # Performs a clean up of build dirs           #
    # ------------------------------------------- #
    def clean_up(self):
        for path in self.cleanup_dirs:
            delete_dir(path)

    # Compile all source files into obj files           #
    # No linking yet                                    #
    # ------------------------------------------------- #
    def compile_source_files(self) -> list:
        # Use active target profile
        target = self.active_profile
        log.info(f'Starting \"{target}\" compile...')

        # Store the results of all operations in this list
        # TODO: Find a better way to do this
        results = list()

        # Gather all source files
        for source in self.build_files['sources']:
            src = source.name

            # Create a hash based on the directory
            # This prevents name collisions with other
            # generated object files, having the same name
            src_hash = str(source).encode('utf-8')
            src_hash_trunc = md5(src_hash).hexdigest()[:8]

            # Create a destination path for object files
            obj_path = f"{src.split('.')[0]}-{src_hash_trunc}.o"
            obj = self.dirs['build'] / obj_path

            # Compile vars
            compiler = self.compiler
            includes = ' '.join(self.include_dirs)
            build_flags = ' '.join(self.build_flags[target])

            # Build the command and split it
            cmd_build_obj = f"{compiler} -c -o \"{obj}\" \"{source}\" {includes} {build_flags}"
            cmd_build_obj = shlex.split(cmd_build_obj)

            # Run and capture output
            process = sp.run(cmd_build_obj, capture_output=True)

            # Check return codes
            if process.returncode == 0:
                log.info(f"\"{target}\" intermediate compile complete")

                if process.stderr:
                    log.info('Captured output: ')
                    log.info(f"\n{process.stderr.decode('utf-8')}")

                results.append(True)
            else:
                log.error('f\"{target} intermediate compile failed\"')
                log.error(f"\n{process.stderr.decode('utf-8')}")

                results.append(False)

        return results

    # Compile all object files into one binary           #
    # -------------------------------------------------- #
    def compile_objects(self):
        # Use active target profile
        target = self.active_profile
        log.info(f'Starting \"{target}\" build...')

        # Glob all object files and add quotes for paths
        objs = get_file_list(self.dirs['build'], '*.o')
        objs = [f'\"{path}\"' for path in objs]

        # Ugly hack to use the selected target as the index for
        # the list of targets which are already stored as paths
        # TODO: Figure out a better way to do this
        target_path = self.root / 'target' / target
        target_index = self.dirs['target'].index(target_path)

        # Change filename extensions based on target build type
        bin_path = self.dirs['target'][target_index] / \
            f'{self.name}.{self.build_type}'

        # Vars for final compile
        compiler = self.compiler
        objs = ' '.join(objs)
        libs = ' '.join(self.library_dirs)
        largs = ' '.join(self.linker_args)
        build_flags = ' '.join(self.build_flags[target])

        # Build command and split
        cmd_build_bin = f"{compiler} -o \"{bin_path}\" {objs} {build_flags} {libs} {largs}"
        cmd_build_bin = shlex.split(cmd_build_bin)

        # Run and capture output
        process = sp.run(cmd_build_bin, capture_output=True)

        # Check return codes
        if process.returncode == 0:
            log.info(f"\"{target}\" final build complete")

            if process.stderr:
                log.info('Captured output: ')
                log.info(f"\n{process.stderr.decode('utf-8')}")
        else:
            log.error('f\"{target} final build failed\"')
            log.error(f"\n{process.stderr.decode('utf-8')}")

    # Build source and object files           #
    # --------------------------------------- #
    def build(self):
        results = self.compile_source_files()

        # Only perform the final compile
        # once all object files have been built
        if (all(res == True for res in results)):
            self.compile_objects()
