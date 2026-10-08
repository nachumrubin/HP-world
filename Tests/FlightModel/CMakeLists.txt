cmake_minimum_required(VERSION 3.16)
project(HPFlightModelTests CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(FLIGHT_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../Source/HPFlight)

add_executable(FlightModelTests
	FlightModelTests.cpp
	${FLIGHT_DIR}/Private/BroomFlightModel.cpp
)
target_include_directories(FlightModelTests PRIVATE ${FLIGHT_DIR}/Public)

if(MSVC)
	target_compile_options(FlightModelTests PRIVATE /W4 /WX)
else()
	target_compile_options(FlightModelTests PRIVATE -Wall -Wextra -Wshadow -Werror)
endif()

enable_testing()
add_test(NAME FlightModelTests COMMAND FlightModelTests)
