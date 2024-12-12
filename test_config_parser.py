import unittest
import subprocess
import os
import sys

class TestConfigToYaml(unittest.TestCase):
    def setUp(self):
        # Путь к скрипту
        self.script = os.path.join(os.path.dirname(__file__), 'config_to_yaml.py')
        self.output_file = 'test_output.yaml'
        # Удалим выходной файл, если существует
        if os.path.exists(self.output_file):
            os.remove(self.output_file)

    def run_parser(self, input_text):
        # Запускаем скрипт с подачей input_text на stdin
        # Результат пишем в self.output_file
        proc = subprocess.Popen(
            [sys.executable, self.script, self.output_file],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        out, err = proc.communicate(input_text)
        return proc.returncode, out, err

    def test_simple_key_value(self):
        input_text = """def hostname = "example.com";
def port = 8080;

Hostname = $hostname$;
Port = $port$;
"""
        code, out, err = self.run_parser(input_text)
        self.assertEqual(code, 0, f"Process failed with error: {err}")
        # Проверим содержимое output.yaml
        with open(self.output_file, 'r', encoding='utf-8') as f:
            yaml_content = f.read()
        self.assertIn('Hostname: "example.com"', yaml_content)
        self.assertIn('Port: 8080', yaml_content)

    def test_arrays(self):
        input_text = """Numbers = [1, 2, 3];
Strings = ["one", "two", "three"];
"""
        code, out, err = self.run_parser(input_text)
        self.assertEqual(code, 0)
        with open(self.output_file, 'r', encoding='utf-8') as f:
            yaml_content = f.read()
        self.assertIn('Numbers:', yaml_content)
        self.assertIn('- 1', yaml_content)
        self.assertIn('- 2', yaml_content)
        self.assertIn('- 3', yaml_content)
        self.assertIn('Strings:', yaml_content)
        self.assertIn('- "one"', yaml_content)
        self.assertIn('- "two"', yaml_content)
        self.assertIn('- "three"', yaml_content)

    def test_comments(self):
        input_text = """'
def name = "Test";
' Ещё комментарий
Value = $name$;

{- 
Многострочный комментарий
-}
Number = 42;
"""
        code, out, err = self.run_parser(input_text)
        self.assertEqual(code, 0)
        with open(self.output_file, 'r', encoding='utf-8') as f:
            yaml_content = f.read()
        # Проверим, что комментарии перенесены
        # Мы ожидаем, что однострочные комментарии преобразуются в # ...
        self.assertIn('# Многострочный комментарий', yaml_content)
        self.assertIn('# Ещё комментарий', yaml_content)
        self.assertIn('# Многострочный комментарий', yaml_content)
        self.assertIn('Value: "Test"', yaml_content)
        self.assertIn('Number: 42', yaml_content)

    def test_undefined_constant_error(self):
        input_text = """Value = $undefined$;"""
        code, out, err = self.run_parser(input_text)
        self.assertNotEqual(code, 0)
        self.assertIn("Undefined constant: undefined", err)

    def test_syntax_error(self):
        input_text = """Invalid line"""
        code, out, err = self.run_parser(input_text)
        self.assertNotEqual(code, 0)
        self.assertIn("Invalid line", err)

    def test_numbers_and_floats(self):
        input_text = """Integer = 123;
FloatVal = 3.14;
BoolTrue = true;
BoolFalse = false;
"""
        code, out, err = self.run_parser(input_text)
        self.assertEqual(code, 0)
        with open(self.output_file, 'r', encoding='utf-8') as f:
            yaml_content = f.read()
        self.assertIn("Integer: 123", yaml_content)
        self.assertIn("FloatVal: 3.14", yaml_content)
        self.assertIn("BoolTrue: true", yaml_content)
        self.assertIn("BoolFalse: false", yaml_content)

    def test_multiple_def_constants(self):
        input_text = """def a = 10;
def b = "string";
DefTest = [$a$, $b$];
"""
        code, out, err = self.run_parser(input_text)
        self.assertEqual(code, 0, err)
        with open(self.output_file, 'r', encoding='utf-8') as f:
            yaml_content = f.read()
        self.assertIn('- 10', yaml_content)
        self.assertIn('- "string"', yaml_content)

if __name__ == "__main__":
    unittest.main()