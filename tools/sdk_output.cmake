# The vendor freetype CMakeLists.txt sets LIBRARY_OUTPUT_PATH inside the SDK.
# Apply after hello_world's project(), when the SDK target already exists.
if(NOT TARGET freetype)
  message(FATAL_ERROR "Pinned reference app must define the freetype target")
endif()
set_target_properties(freetype PROPERTIES
  ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/sdk-libraries")
