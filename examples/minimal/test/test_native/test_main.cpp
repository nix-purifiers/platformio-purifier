#include <Arduino.h>
#include <unity.h>
void setUp() {}
void tearDown() {}
void test_answer() { TEST_ASSERT_EQUAL_INT(42,42); }
void setup() { UNITY_BEGIN(); RUN_TEST(test_answer); UNITY_END(); }
void loop() {}
