---
name: create-test-cases
description: 
  This skill generates test cases for a given function or class in Python. It analyzes the code and produces unit tests that cover various scenarios, including edge cases and expected behavior.
---

When this skill is invoked, it will analyze the provided Python function or class and generate a set of unit tests. The generated tests will be designed to cover different input scenarios, including normal cases, edge cases, and potential error conditions.

Test case format:
Each test case will be structured as a Python function using the `pytest` framework.
1. **Test Case ID**: A unique identifier for the test case.
2. **Description**: A brief description of what the test case is validating.
3. **Input**: The input values or parameters for the function/class being tested.
4. **Expected Output**: The expected result or behavior of the function/class for the given input.
5. **Severity**: The severity level of the test case (e.g., high, medium, low).