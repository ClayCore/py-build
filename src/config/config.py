from utils.logger import log
from .depdict import DepDict
from flatdict import FlatDict  # type: ignore
from pathlib import Path
from typing import Tuple, Any
import yaml  # type: ignore


class Config(object):
    # ======================================== #
    # Base config file class                   #
    # ======================================== #
    def __init__(self, path: Path):
        # Basic project setup           #
        # ----------------------------- #
        self.config_path = path.resolve()

        # Loads a processed and raw config file
        (self.config, self.raw_config) = self.load_config(self.config_path)

        # Main project directory extrapolated from
        # the config path. All directories in the build file
        # are relative to this path. (unless specified otherwise)
        self.root = self.config_path.parent

        # Project configuration           #
        # ------------------------------- #

        # Metadata
        self.name = self.get_value('project:name')
        self.authors = self.get_value('project:authors')
        self.version = self.get_value('project:version')
        self.language = self.get_value('project:language')

        # Directory structure
        self.dirs = self.get_value('project:dirs')

        # Resolves all paths
        self.resolve_dirs()

        # Building
        self.build_files = self.get_value('project:setup:files')
        self.build_type = self.get_value('project:setup:type')
        self.compiler = self.get_value('project:setup:compiler')
        self.profiles = self.get_value('project:setup:profiles')

        # Currently active target profile
        self.active_profile = ''

        # Resolve all files for building
        self.resolve_files()

        # Dependency management           #
        # ------------------------------- #

        # Raw list of dependencies from the config file
        self.raw_deps = self.get_value_raw('dependencies')
        self.deps = None

        # Include and library directories
        # pulled from dependencies
        self.include_dirs = None
        self.library_dirs = None

        # Linker arguments necessary for building
        self.linker_args = None

        # Resolves all variables above
        self.process_deps()

        # Push profile target directory
        # and push build flags according to profile
        self.build_flags = self.build_profile_setup()

        # Clean-up directories
        self.cleanup_dirs = [self.dirs['build'], self.dirs['target']]

    # Resolves all directories to project root           #
    # /unless/ they're already absolute paths            #
    # -------------------------------------------------- #
    def resolve_dirs(self):
        log.info("Resolving project directories...")

        for key, path in self.dirs.items():
            # At this point the 'target' directory
            # is already split according to build profiles.
            # Treat it differently from the rest
            if isinstance(path, list):
                temp_paths = []

                # Check each path whether
                # it's absolute or relative
                for p in path:
                    exists = Path(p).is_absolute()
                    is_absolute = Path(p).exists()

                    if exists and is_absolute:
                        # No need for any transforms
                        temp_paths.append(Path(p))
                    elif not is_absolute:
                        # Make it relative to project root
                        temp_paths.append(self.root / p)

                # Re-assign to dictionary
                self.dirs[key] = temp_paths
            else:
                # Perform same checks
                exists = Path(path).exists()
                is_absolute = Path(path).is_absolute()

                if exists and is_absolute:
                    # No need for any transforms
                    self.dirs[key] = Path(path)
                elif not is_absolute:
                    # Make it relative to project root
                    self.dirs[key] = self.root / path

    # Resolves all build files from config           #
    # ---------------------------------------------- #
    def resolve_files(self):
        log.info('Resolving source and header files...')

        for key, paths in self.build_files.items():
            temp_paths = []

            for p in paths:
                # Check if a path is absolute and exists
                exists = Path(p).exists()
                is_absolute = Path(p).is_absolute()

                if exists and is_absolute:
                    temp_paths.append(Path(p))
                elif not exists and is_absolute:
                    err = f'File \"{p}\" not found'
                    log.error(err)
                    raise FileNotFoundError(err).with_traceback()

                # We don't care if a given path exists yet or not
                # since we're canonicalizing them anyways
                if not is_absolute:
                    # Get source files
                    if key == 'sources':
                        new_path = self.dirs['source'] / p
                        temp_paths.append(new_path)

                    # Get header files
                    if key == 'include':
                        new_path = self.dirs['include'] / p
                        temp_paths.append(new_path)

                # Put all found files back into the dict
                self.build_files[key] = temp_paths

    # Resolve paths, add switches and collect dirs           #
    # using a utility dependency dictionary                  #
    # ------------------------------------------------------ #
    def process_deps(self):
        log.info('Processing dependencies...')

        self.deps = DepDict(self.raw_deps)

        # Resolve all paths
        self.deps.resolve(self.dirs)

        # Fetch include directories
        include_dirs = self.deps.get_include_dirs()
        include_dirs = self.deps.add_include_switch(self.dirs)

        self.include_dirs = include_dirs

        # Fetch library directories
        library_dirs = self.deps.get_library_dirs()
        library_dirs = self.deps.add_library_switch(self.dirs)

        self.library_dirs = library_dirs

        # Fetch linker arguments
        self.linker_args = self.deps.get_linker_args()

    # Push build profile to target directory
    # and get a list of  build flags for each profile           #
    # --------------------------------------------------------- #
    def build_profile_setup(self):
        log.info('Setting up target directories and build flags...')

        build_flags = dict()
        target_dirs = []

        for profile in list(self.profiles):
            # Canonicalize paths before pushing
            new_path = self.root / self.dirs['target'] / profile
            target_dirs.append(new_path)

        # Re-assign into main directory map
        self.dirs['target'] = target_dirs

        # Fetch build flags from build profile information
        for profile_name, flags in self.profiles.items():
            build_flags[profile_name] = flags

        return build_flags

    # Selects a specific target from config file          #
    # using command-line arguments                        #
    # --------------------------------------------------- #
    def set_active_profile(self, target: str):
        if target in list(self.profiles):
            # Re-assign active profile to the one found
            self.active_profile = target
        else:
            log.error(f'Target \"{target}\"')

            default_target = list(self.profiles[0])
            log.error(f'Defaulting to \"{default_target}\"')

            self.active_profile = default_target

    # Load and process configuration file            #
    # returning either a nested dictionary           #
    # or a flatdict.FlatDict                         #
    # ---------------------------------------------- #
    def load_config(self, path: Path) -> Tuple[FlatDict, dict]:
        log.info('Loading project configuration...')

        result = (FlatDict(), dict())
        with open(path) as file:
            raw_dump = yaml.load(file, Loader=yaml.FullLoader)
            result = (FlatDict(raw_dump), raw_dump)

        # Make sure to validate what we received
        # from the yaml dump
        if result[0] is None or result[1] is None:
            message = f'Unable to parse configuration file'
            log.error(message)
            raise IOError(message).with_traceback()

        return result

    # Acquire a value from the flat dictionary           #
    # -------------------------------------------------- #
    def get_value(self, key: str) -> Any:
        value = self.config.get(key)

        if value is None:
            log.warning(f'Key \"{key}\" not found in build file')
            return None
        else:
            return value

    # Traverse the yaml dump recursively                #
    # and retrieve value given a distinct key           #
    # ------------------------------------------------- #
    def find_config_key(self, key: str, src: Any) -> Any:
        is_dict = isinstance(src, dict)
        is_list = isinstance(src, list)

        for k, v in (src.items if is_dict else enumerate(src) if is_list else []):
            if k == key:
                yield v
            elif isinstance(v, (dict, list)):
                for subkey in self.find_config_key(key, v):
                    yield subkey

    # Internally calls into self.find_config_key            #
    # and makes sure the value we get isn't empty           #
    # ----------------------------------------------------- #
    def get_value_raw(self, key: str) -> Any:
        for value in self.find_config_key(key, self.raw_config):
            if value is None:
                log.warning(f'Key \"{key}\" not found in build file')
                return None
            else:
                return value
