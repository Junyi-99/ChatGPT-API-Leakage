# See https://pre-commit.com for more information
# See https://pre-commit.com/hooks.html for more hooks
repos:
    - repo: https://github.com/PyCQA/isort
      rev: 5.13.2
      hooks:
          - id: isort
            args: [--profile, black]

    # Using this mirror lets us use mypyc-compiled black, which is about 2x faster
    - repo: https://github.com/psf/black-pre-commit-mirror
      rev: 24.4.2
      hooks:
          - id:
                black
                # It is recommended to specify the latest version of Python
                # supported by your project here, or alternatively use
                # pre-commit's default_language_version, see
                # https://pre-commit.com/#top_level-default_language_version
            language_version: python3.12
            args: ["--line-length", "200", "--exclude", "migrations/"]

    -   repo: https://github.com/astral-sh/ruff-pre-commit
        rev: v0.0.285
        hooks:
        -   id: ruff
            alias: autoformat
            args: [--fix]

    - repo: https://github.com/pycqa/flake8
      rev: 7.1.0
      hooks:
          - id: flake8
            exclude: ^tests/(data|examples)/

    - repo: https://github.com/pre-commit/mirrors-mypy
      rev: v1.10.1
      hooks:
          - id: mypy
            args: [--ignore-missing-imports, --no-namespace-packages]

    - repo: https://github.com/pre-commit/pre-commit-hooks
      rev: v3.2.0
      hooks:
          - id: trailing-whitespace
          - id: end-of-file-fixer
          - id: check-yaml
          - id: check-added-large-files
