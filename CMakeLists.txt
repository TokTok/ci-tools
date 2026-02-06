cmake_minimum_required(VERSION 3.10)

set(CMAKE_MODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR}/cmake)

project(
  CiTools
  VERSION 0.8.3
  LANGUAGES CXX)

# Project name lowercase
string(TOLOWER ${PROJECT_NAME} BINARY_NAME)

set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(CMAKE_UNITY_BUILD ON)
set(CMAKE_UNITY_BUILD_BATCH_SIZE 8)

add_definitions(-DQT_NO_CAST_FROM_BYTEARRAY)
add_definitions(-DQT_NO_CAST_TO_ASCII)
add_definitions(-DQT_NO_CAST_FROM_ASCII)
add_definitions(-DQT_NO_NARROWING_CONVERSIONS_IN_CONNECT)
add_definitions(-DQT_NO_URL_CAST_FROM_STRING)
add_definitions(-DQT_NO_CONTEXTLESS_CONNECT)
add_definitions(-DQT_MESSAGELOGCONTEXT=1)

find_package(QT NAMES Qt6 REQUIRED COMPONENTS Widgets)
find_package(Qt${QT_VERSION_MAJOR} REQUIRED COMPONENTS Widgets)

set(PROJECT_SOURCES src/main.cpp)

if(COMMAND qt_policy)
  # set QTP0002 policy: target properties that specify Android-specific paths
  # may contain generator expressions
  qt_policy(SET QTP0002 NEW)
endif()

qt_add_executable(${BINARY_NAME} ${PROJECT_SOURCES})

target_link_libraries(${BINARY_NAME} PRIVATE Qt${QT_VERSION_MAJOR}::Widgets)

target_include_directories(${BINARY_NAME} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

set_target_properties(
  ${BINARY_NAME}
  PROPERTIES
    QT_ANDROID_TARGET_SDK_VERSION 34
    QT_ANDROID_MIN_SDK_VERSION 24
    QT_ANDROID_PACKAGE_SOURCE_DIR
    "${CMAKE_CURRENT_SOURCE_DIR}/platform/android/qt-${Qt6Core_VERSION}")

include(Installation)
