{
  description = "LOTB: Lord of telegram bots";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        py = pkgs.python313;
        pyPkgs = py.pkgs;
        lotbVersion = ((builtins.fromTOML (builtins.readFile ./pyproject.toml)).tool.poetry.version);
        lotbName = ((builtins.fromTOML (builtins.readFile ./pyproject.toml)).tool.poetry.name);
        dockerRegistry = "ghcr.io/brokenpip3";
      in
      {
        formatter = pkgs.nixpkgs-fmt;

        packages.${lotbName} = pyPkgs.buildPythonApplication {
          pname = lotbName;
          version = lotbVersion;
          src = ./.;
          format = "pyproject";
          nativeBuildInputs = with pyPkgs; [ poetry-core ];
          propagatedBuildInputs = with pyPkgs; [
            apscheduler
            feedparser
            litellm
            mcp
            python-dateutil
            python-telegram-bot
            typing-extensions
          ];
          nativeCheckInputs = with pyPkgs; [
            pytest
            pytest-asyncio
            pytest-cov
            types-python-dateutil
          ];
          # Apparently this is not working
          disabledTests = [
            "test_unsplash_search_success"
            "test_unsplash_search_no_results"
            "test_unsplash_search_api_error"
          ];
          checkPhase = ''
            runHook preCheck
            pytest -s -v -k 'not unsplash'
            runHook postCheck
          '';
        };

        packages.default = self.packages.${system}.${lotbName};

        packages.dockerimg = pkgs.dockerTools.buildImage {
          name = "${dockerRegistry}/${lotbName}";
          tag = lotbVersion;
          created = "now";
          copyToRoot = self.packages.${system}.default;
          config = {
            Labels = {
              "maintainer" = "brokenpip3";
              "description" = "Docker image for ${lotbName}";
              "version" = lotbVersion;
              "org.opencontainers.image.authors" = "brokenpip3 <brokenpip3@gmail.com>";
              "org.opencontainers.image.title" = "lotb";
              "org.opencontainers.image.description" = "Lord of telegram bots";
              "org.opencontainers.image.url" = "ghcr.io/brokenpip3/lotb";
              "org.opencontainers.image.source" = "https://github.com/brokenpip3/lotb";
            };
          };
        };

        devShells.default = pkgs.mkShell {
          inputsFrom = [ self.packages.${system}.${lotbName} ];
          packages = with pkgs; [
            py
            ruff
            mypy
            pre-commit
            go-task
          ];
          PYTHONDONTWRITEBYTECODE = 1;
        };
      }
    );
}
