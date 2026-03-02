def test_mainwindow_shutdown_no_exceptions(qtbot):
    from vector_inspector.ui.main_window import MainWindow

    main = MainWindow()
    qtbot.addWidget(main)
    # Ensure splash is disabled to avoid blocking modal dialogs during tests
    try:
        main.settings_service.set("hide_splash_window", True)
    except Exception:
        pass

    # show and then close; this exercises closeEvent ordering
    main.show()
    qtbot.waitExposed(main)
    main.close()
