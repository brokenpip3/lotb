# check whether the flake evaluates and run its tests
flake-check:
    nix flake check

# update all flake inputs
flake-update-all:
    @printf "\n> Updating all flake inputs\n\n"
    @nix flake update

# update one flake input like nixpkgs or flake-utils
flake-update-one INPUT:
    @printf "\n> Updating flake input {{INPUT}}\n\n"
    @nix flake lock --update-input {{INPUT}}

# initialize pre-commit
pre-commit:
    pre-commit install

# run pytest with optional arguments
pytest *ARGS:
    pytest -v -s {{ARGS}}

# create coverage report
coverage:
    pytest --cov=lotb --cov-report=term-missing

# run mypy
mypy:
    mypy lotb

# run ruff formatter and linter
fmt:
    ruff check --fix
    ruff format

# run the app locally
local:
    nix build .#lotb
    ./result/bin/lotb --config config.toml

# run all tests
[parallel]
test: fmt mypy pytest

# temp override version in pyproject.toml if OVERRIDE_VERSION is set
docker-version:
    @if [ -n "${OVERRIDE_VERSION}" ]; then \
        sed -i '3s/^version = "[^"]*"/version = "'"$OVERRIDE_VERSION"'"/' pyproject.toml; \
    fi

# build docker image from nix
docker-build: docker-version
    nix build .#dockerimg
    docker load < result

# push docker image
docker-push:
    @export IMAGE=$(docker images | grep -E "lotb" | awk '{print $1":"$2}' | head -n 1) && \
    docker push $IMAGE

# restart container
docker-compose-recreate:
    docker compose down
    docker compose up -d

# rebuild and restart container
docker-revamp: docker-build docker-compose-recreate
