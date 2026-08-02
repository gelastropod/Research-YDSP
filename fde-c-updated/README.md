# Ratcheted FDE V1 (in C)

See [fde-v1](/fde-v1/).

## Requirements

- `gcc`
- `libmbedtls-dev` (run `sudo apt install libmbedtls-dev` on Linux)

## Organisation

Files are split into `src` and `tests` directories.

- `src/`: Source files implementing the code declared in header files
- `tests/`: Test files that verify the code declared in header files

Other directories:

- `include/`: Header files
- `obj/`: Local directory created by `make` for object files
- `build/`: Local directory created by `make` for output binaries
- `scripts/`: Bash scripts for testing code

## Building

```bash
make
```

This builds all executables into `build/`. To remove build artifacts:

```bash
make clean
```

## Running tests

Use `scripts/run.sh` with whatever test you want to use. For example:

```bash
scripts/run.sh test_primitives test_runtime
```

## Results

### test_runtime

No significant differences between runtime for sector-scope and global-scope ratcheting found.
