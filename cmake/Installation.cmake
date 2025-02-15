# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2019 by The qTox Project Contributors
# Copyright © 2024-2025 The TokTok team.

#############################################################################
#
# :: Installation
#
#############################################################################

if(NOT PROJECT_ORG)
  set(PROJECT_ORG "chat.tox")
endif()

if(APPLE)
  set_target_properties(${BINARY_NAME} PROPERTIES
    ${BUNDLE_ID_OPTION}
    MACOSX_BUNDLE_BUNDLE_VERSION ${PROJECT_VERSION}
    MACOSX_BUNDLE_SHORT_VERSION_STRING ${PROJECT_VERSION_MAJOR}.${PROJECT_VERSION_MINOR}
    MACOSX_BUNDLE_INFO_PLIST "${CMAKE_SOURCE_DIR}/platform/macos/Info.plist"
    MACOSX_BUNDLE TRUE
    WIN32_EXECUTABLE TRUE
  )

  set(BUNDLE_PATH "${CMAKE_BINARY_DIR}/${BINARY_NAME}.app")

  list(APPEND PROJECT_ICONS "resources/images/icons/${BINARY_NAME}.icns")

  foreach(icon ${PROJECT_ICONS})
    install(FILES ${icon} DESTINATION ${BUNDLE_PATH}/Contents/Resources/)
  endforeach()

  install(CODE "
  message(STATUS \"Creating dmg image\")
  execute_process(COMMAND ${CMAKE_SOURCE_DIR}/platform/macos/createdmg ${PROJECT_NAME} ${CMAKE_SOURCE_DIR} ${BUNDLE_PATH})
  " COMPONENT Runtime
  )
elseif(WIN32)
  install(CODE "
  message(STATUS \"Installer can be created using platform/windows/${BINARY_NAME}64.nsi\")
  " COMPONENT Runtime
  )
else()
  include(GNUInstallDirs)
  # follow the xdg-desktop specification
  install(TARGETS ${BINARY_NAME}
    BUNDLE DESTINATION .
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
  )
  install(FILES "platform/linux/${PROJECT_ORG}.${PROJECT_NAME}.appdata.xml" DESTINATION "${CMAKE_INSTALL_DATAROOTDIR}/metainfo")
  install(FILES "platform/linux/${PROJECT_ORG}.${PROJECT_NAME}.desktop" DESTINATION "${CMAKE_INSTALL_DATAROOTDIR}/applications")

  # Install application icons according to the XDG spec
  set(ICON_SIZES 14 16 22 24 32 36 48 64 72 96 128 192 256 512)
  foreach(size ${ICON_SIZES})
    set(path_from "resources/images/icons/${size}x${size}/${BINARY_NAME}.png")
    set(path_to "share/icons/hicolor/${size}x${size}/apps/")
    install(FILES ${path_from} DESTINATION ${path_to})
  endforeach(size)

  # process the icon, compress if enabled
  set(SVG_SRC "${CMAKE_SOURCE_DIR}/resources/images/icons/${BINARY_NAME}.svg")
  install(FILES "${SVG_SRC}" DESTINATION "share/icons/hicolor/scalable/apps")
endif()
