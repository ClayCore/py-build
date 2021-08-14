from pathlib import Path
from utils.logger import log


class DepDict(dict):
    # ======================================= #
    # Dependency dictionary                   #
    # for managing dependency paths           #
    # ======================================= #
    def __init__(self, *arg, **kw):
        super().__init__(*arg, **kw)

    # Resolves all paths for dependencies                   #
    # this should canonicalize all relative paths           #
    # however, they should be touched if                    #
    # they're already absolute paths                        #
    # ----------------------------------------------------- #
    def resolve(self, dirs: dict):
        log.info('Resolving paths for dependencies...')

        for key, subkey in self.items():
            # Check the 'enabled' and 'system-wide' flags
            is_enabled = subkey['enabled']
            is_system_wide = subkey['system_wide']
            has_library = subkey['header_only']

            if is_system_wide and is_enabled:
                # Check all paths to make sure they're already
                # canonicalized and that they exist
                for path in subkey['paths'].values():
                    exists = Path(path).exists()
                    is_absolute = Path(path).is_absolute()

                    if not is_absolute:
                        err = f"Path: \"{path}\" not found."
                        log.error(err)
                        raise FileNotFoundError(err).with_traceback()

                    if not exists:
                        err = f"Path: \"{path}\" doesn't exist."
                        log.error(err)
                        raise FileNotFoundError(err).with_traceback()

            # Resolve all relative paths
            elif not is_system_wide and is_enabled:
                for path in subkey['paths'].values():
                    # NOTE: 'key' is the name of the package
                    new_path = dirs['deps'] / key / path

                    # Re-assign new path
                    self[key]['paths'][path] = new_path

                # Resolve library directories
                if not has_library:
                    new_libs = []
                    for path in subkey['libs']:
                        lib_path = subkey['paths']['lib']
                        new_path = dirs['deps'] / key / lib_path / path

                        new_libs.append(new_path)

                    self[key]['libs'] = new_libs
            else:
                continue

    # Return a all include directories for deps           #
    # --------------------------------------------------- #
    def get_include_dirs(self, dirs: dict) -> list:
        log.info('Fetching include directories...')

        includes = []
        for subkey in self.values():
            # For linux compatibility
            # check whether headers are stored
            # in a system directory
            is_system_wide = subkey['system_wide']

            # Check 'enabled flag'
            is_enabled = subkey['enabled']

            if is_enabled and not is_system_wide:
                # Fetch local include dirs
                # relative to project root
                include_dir = subkey['paths']['include']

                includes.append(f'\"{include_dir}\"')

            if is_enabled and is_system_wide:
                # Fetch system-wide include directories
                include_dir = subkey['search_paths']['include']

                includes.append(f'\"{include_dir}\"')

        # Append main project source and include directories
        includes.append(f"\"{dirs['include']}\"")
        includes.append(f"\"{dirs['source']}\"")

        return includes

    # Return a all library directories for deps           #
    # --------------------------------------------------- #
    def get_library_dirs(self, dirs: dict) -> list:
        log.info('Fetching library directories...')

        libs = []
        for subkey in self.values():
            # For linux compatibility
            # check whether libraries are stored
            # in a system directory
            is_system_wide = subkey['system_wide']

            # Check 'enabled' flag
            is_enabled = subkey['enabled']

            if is_enabled and not is_system_wide:
                # Fetch local library dirs
                # relative to project root
                library_dir = subkey['paths']['lib']

                libs.append(f'\"{library_dir}\"')

            if is_enabled and is_system_wide:
                # Fetch system-wide library directories
                library_dir = subkey['search_paths']['lib']

                libs.append(f'\"{library_dir}\"')

        return libs

    # Prepend '-I' switch to include directories           #
    # ---------------------------------------------------- #
    def add_include_switch(self, dirs: list) -> list:
        log.info("Adding \'-I\' switch to include directories...")
        paths = [f'-I{path}' for path in dirs]

        return paths

    # Prepend '-L' switch to library directories           #
    # ---------------------------------------------------- #
    def add_library_switch(self, dirs: list) -> list:
        log.info("Adding \'-L\' switch to library directories...")
        paths = [f'-L{path}' for path in dirs]

        return paths

    # Get all linker arguments for dependencies           #
    # --------------------------------------------------- #
    def get_linker_args(self) -> list:
        log.info('Fetching linker arguments...')

        args = []
        for subkey in self.values():
            # Check the dependency flags
            is_enabled = subkey['enabled']
            has_library = subkey['header_only']

            if is_enabled and has_library:
                # Add all arguments from the subkey
                for arg in subkey['args']:
                    args.append(arg)

        return args
