{
  description = "LOTB: Lord of telegram bots";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-24.11";
    flake-utils.url = "github:numtide/flake-utils";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        inherit (poetry2nix.lib.mkPoetry2Nix { inherit pkgs; }) mkPoetryApplication;
        lotbVersion = ((builtins.fromTOML (builtins.readFile ./pyproject.toml)).tool.poetry.version);
        lotbName = ((builtins.fromTOML (builtins.readFile ./pyproject.toml)).tool.poetry.name);
        dockerRegistry = "ghcr.io/brokenpip3";
      in
      {
        formatter = nixpkgs.legacyPackages.${system}.nixpkgs-fmt;

        packages = {
          "${lotbName}" = mkPoetryApplication {
            python = pkgs.python3;
            projectDir = self;
            checkPhase = "pytest -s -v";
          };
          default = self.packages.${system}."${lotbName}";
        };

        packages.dockerimg = pkgs.dockerTools.buildImage
          {
            name = "${dockerRegistry}/${lotbName}";
            tag = "${lotbVersion}";
            created = "now";
            copyToRoot = self.packages.${system}.default;
            config = {
              Labels = {
                "maintainer" = "brokenpip3";
                "description" = "Docker image for ${lotbName}";
                "version" = "${lotbVersion}";
                "org.opencontainers.image.authors" = "brokenpip3 <brokenpip3@gmail.com>";
                "org.opencontainers.image.title" = "lotb";
                "org.opencontainers.image.description" = "Lord of telegram bots";
                "org.opencontainers.image.url" = "ghcr.io/brokenpip3/lotb";
                "org.opencontainers.image.source" = "https://github.com/brokenpip3/lotb";
              };
            };
          };


        devShells.default = pkgs.mkShell {
          inputsFrom = [ self.packages.${system}.lotb ];
          packages = with pkgs; [
            python3
            poetry
            pre-commit
            ruff
            mypy
            python311Packages.pytest-cov
            python311Packages.flake8
            go-task
          ];
          PYTHONDONTWRITEBYTECODE = 1;
          POETRY_VIRTUALENVS_IN_PROJECT = 1;
        };
      });
}
