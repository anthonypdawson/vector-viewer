if __name__ == "__main__":
    from vector_inspector._cli import parse_cli_args

    # Handle --version / --help before importing Qt/GUI modules.
    parse_cli_args()

    from vector_inspector.main import main

    main()
