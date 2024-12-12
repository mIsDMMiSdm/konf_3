import argparse
import sys
import re


class ConfigParser:
    def __init__(self):
        self.constants = {}
        self.lines = []
        self.parsed = {}
        self.comments_for_next = []

    def parse(self, text):
        # Разделим по строкам
        self.lines = text.splitlines()
        result = {}
        for line in self.lines:
            stripped = line.strip()
            if not stripped:
                continue
            pass

        # Упростим обработку: сначала извлечём многострочные комментарии
        text = self.extract_multiline_comments(text)
        # Теперь text содержит многострочные комментарии заменённые на
        # строки вида `' Многострочный комментарий...`

        # Повторим процедуру
        self.lines = text.splitlines()
        for line in self.lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Проверка на комментарий
            if stripped.startswith("'"):
                # Однострочный комментарий
                # Сохраним для следующей конструкции
                self.comments_for_next.append(stripped.lstrip("'").strip())
                continue
            if stripped.startswith("def "):
                self.define_constant(stripped)
                continue
            # Попытка парсинга пары ключ-значение
            if '=' in stripped and stripped.endswith(';'):
                key_val_line = stripped
                key, val = self.parse_key_value(key_val_line)
                val_resolved = self.resolve_value(val)
                # Сохраняем вместе с комментариями
                if key in result:
                    raise ValueError(f"Duplicate key: {key}")
                result[key] = {
                    "__value__": val_resolved,
                    "__comments__": self.comments_for_next
                }
                self.comments_for_next = []
            else:
                # Неизвестная конструкция
                raise ValueError(f"Invalid line: {line}")

        self.parsed = result
        return result

    def extract_multiline_comments(self, text):
        # Найдём все вхождения {-, -}
        # Заменим каждое многострочное комментариев на строки с ' на каждой строчке
        pattern = r"\{\-(.*?)\-\}"
        matches = re.findall(pattern, text, flags=re.DOTALL)
        for m in matches:
            # Разобьём комментарий по строкам и превратим каждую в однострочный
            lines = m.split('\n')
            repl = ""
            for l in lines:
                l_stripped = l.strip()
                if l_stripped:
                    repl += "'" + l_stripped + "\n"
                else:
                    repl += "'\n"
            # Удалим завершающий \n
            if repl.endswith('\n'):
                repl = repl[:-1]
            # Заменим в исходном тексте
            text = re.sub(r"\{\-.*?\-\}", repl, text, count=1, flags=re.DOTALL)
        return text

    def define_constant(self, line):
        match = re.match(r"def\s+(\w+)\s*=\s*(.+);", line)
        if not match:
            raise ValueError(f"Invalid constant definition: {line}")
        name, value = match.groups()
        val = self.resolve_value(value)
        self.constants[name] = val
        # Константы тоже могут получать комментарии
        # Можно их просто игнорировать или тоже хранить,
        # для простоты тут не будем их вставлять в YAML.
        self.comments_for_next = []

    def parse_key_value(self, line):
        # Пример: key = value;
        match = re.match(r"(\w+)\s*=\s*(.+);", line)
        if not match:
            raise ValueError(f"Invalid key-value line: {line}")
        return match.groups()

    def resolve_value(self, val):
        val = val.strip()
        # Проверка на вычисление константы
        if val.startswith("$") and val.endswith("$"):
            name = val[1:-1]
            if name not in self.constants:
                raise ValueError(f"Undefined constant: {name}")
            return self.constants[name]

        # Строка
        if val.startswith('"') and val.endswith('"'):
            return val.strip('"')

        # Массив
        if val.startswith('[') and val.endswith(']'):
            inner = val[1:-1].strip()
            if not inner:
                return []
            parts = [p.strip() for p in inner.split(",")]
            return [self.resolve_value(p) for p in parts]

        # Число (целое или float)
        if re.match(r"^\d+$", val):
            return int(val)
        if re.match(r"^\d+\.\d+$", val):
            return float(val)

        # Иначе просто возвращаем как есть (может bool или что-то ещё)
        # Можно добавить поддержку true/false
        if val.lower() == "true":
            return True
        if val.lower() == "false":
            return False

        # Если ничего не подошло, вернём как строку
        return val

    def to_yaml(self):
        # Рекурсивно выводим данные с комментариями
        # self.parsed: dict {key: {"__value__": value, "__comments__": [comments]}}
        return self.dump_dict(self.parsed, indent=0)

    def dump_dict(self, d, indent=0):
        lines = []
        for k, v in d.items():
            comments = v.get("__comments__", [])
            val = v.get("__value__")

            # Выведем комментарии
            for c in comments:
                lines.append(" " * indent + "# " + c)

            # Проверим тип val
            if isinstance(val, dict):
                # Словарь
                lines.append(" " * indent + f"{k}:")
                lines.extend(self.dump_dict({ik: {"__value__": iv, "__comments__": []} for ik, iv in val.items()},
                                            indent=indent + 2))
            elif isinstance(val, list):
                # Список
                lines.append(" " * indent + f"{k}:")
                for item in val:
                    # Перед элементами списка тоже можно вставлять комментарии,
                    # но у нас их сейчас нет. Если бы были, пришлось бы хранить иначе.
                    if isinstance(item, dict):
                        # Если элемент списка тоже словарь
                        lines.append(" " * (indent + 2) + "-")
                        lines.extend(
                            self.dump_dict({ik: {"__value__": iv, "__comments__": []} for ik, iv in item.items()},
                                           indent=indent + 4))
                    else:
                        # Просто скалярное значение
                        lines.append(" " * (indent + 2) + f"- {self.scalar_to_str(item)}")
            else:
                # Скалярное значение
                lines.append(" " * indent + f"{k}: {self.scalar_to_str(val)}")
        return lines

    def scalar_to_str(self, val):
        if isinstance(val, str):
            # Если строка содержит пробелы или не ascii - в кавычки
            # Для простоты всегда в кавычки
            return '"' + val.replace('"', '\\"') + '"'
        if isinstance(val, bool):
            return "true" if val else "false"
        return str(val)


def main():
    parser = argparse.ArgumentParser(description="Convert config to YAML with comments.")
    parser.add_argument("output", help="Output YAML file path")
    args = parser.parse_args()

    input_text = sys.stdin.read()
    config_parser = ConfigParser()
    try:
        config_parser.parse(input_text)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    yaml_lines = config_parser.to_yaml()
    with open(args.output, "w", encoding="utf-8") as f:
        for line in yaml_lines:
            f.write(line + "\n")


if __name__ == "__main__":
    main()
