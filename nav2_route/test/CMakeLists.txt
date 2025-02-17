# Route planner benchmarking script
add_executable(performance_benchmarking performance_benchmarking.cpp)
target_link_libraries(performance_benchmarking
  ${library_name}
)
ament_target_dependencies(performance_benchmarking
  ${dependencies}
)
install(TARGETS
  performance_benchmarking
  RUNTIME DESTINATION lib/${PROJECT_NAME}
)

# Test utilities and basic types
ament_add_gtest(test_utils_and_types
  test_utils_and_types.cpp
)
ament_target_dependencies(test_utils_and_types
  ${dependencies}
)
target_link_libraries(test_utils_and_types
  ${library_name}
)

# Test edge scorer + plugins
ament_add_gtest(test_edge_scorers
  test_edge_scorers.cpp
)
ament_target_dependencies(test_edge_scorers
  ${dependencies}
)
target_link_libraries(test_edge_scorers
  ${library_name} edge_scorers
)

# Test path converter
ament_add_gtest(test_path_converter
  test_path_converter.cpp
)
ament_target_dependencies(test_path_converter
  ${dependencies}
)
target_link_libraries(test_path_converter
  ${library_name}
)

# Test node spatial tree
ament_add_gtest(test_spatial_tree
  test_spatial_tree.cpp
)
ament_target_dependencies(test_spatial_tree
  ${dependencies}
)
target_link_libraries(test_spatial_tree
  ${library_name}
)

# Test operation manager + plugins
ament_add_gtest(test_operations
  test_operations.cpp
)
ament_target_dependencies(test_operations
  ${dependencies}
)
target_link_libraries(test_operations
  ${library_name} route_operations
)

# Test graph loader
ament_add_gtest(test_graph_loader
    test_graph_loader.cpp
)
ament_target_dependencies(test_graph_loader
    ${dependencies}
)
target_link_libraries(test_graph_loader
    ${library_name}
)

# Test geojson parser
ament_add_gtest(test_geojson_graph_file_loader
    test_geojson_graph_file_loader.cpp
)
ament_target_dependencies(test_geojson_graph_file_loader
  ${dependencies}
)
target_link_libraries(test_geojson_graph_file_loader
  ${library_name} graph_file_loaders
)

# Test collision monitor seperately due to relative complexity
ament_add_gtest(test_collision_operation
  test_collision_operation.cpp
)
ament_target_dependencies(test_collision_operation
  ${dependencies}
)
target_link_libraries(test_collision_operation
  ${library_name} route_operations
)

# Test route planner
ament_add_gtest(test_route_planner
  test_route_planner.cpp
)
ament_target_dependencies(test_route_planner
  ${dependencies}
)
target_link_libraries(test_route_planner
  ${library_name} edge_scorers
)

# Test goal intent extractor
ament_add_gtest(test_goal_intent_extractor
  test_goal_intent_extractor.cpp
)
ament_target_dependencies(test_goal_intent_extractor
  ${dependencies}
)
target_link_libraries(test_goal_intent_extractor
  ${library_name}
)

# Test route tracker
ament_add_gtest(test_route_tracker
  test_route_tracker.cpp
)
ament_target_dependencies(test_route_tracker
  ${dependencies}
)
target_link_libraries(test_route_tracker
  ${library_name}
)

# Test route server
ament_add_gtest(test_route_server
  test_route_server.cpp
)
ament_target_dependencies(test_route_server
  ${dependencies}
)
target_link_libraries(test_route_server
  ${library_name}
)
