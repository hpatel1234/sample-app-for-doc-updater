import os
import javalang
import argparse
from neomodel import StructuredNode, StringProperty, RelationshipTo, RelationshipFrom, config, db

# Neo4j config (set via env or directly)
config.DATABASE_URL = "neo4j://neo4j:neo4j123@localhost:7687"
config.DATABASE_NAME ="neo4j"

def clear_existing_graph():
    db.cypher_query("""
    MATCH (n) DETACH DELETE n
    """)
# === Node Definitions ===
class Field(StructuredNode):
    name = StringProperty(unique_index=True)
    type = StringProperty()
    belongs_to = RelationshipFrom('Class', 'HAS_FIELD')


class Method(StructuredNode):
    name = StringProperty(unique_index=True)
    code = StringProperty()
    return_type = StringProperty()
    visibility = StringProperty()
    parameters = StringProperty()

    belongs_to = RelationshipFrom('Class', 'HAS_METHOD')
    calls = RelationshipTo('Method', 'CALLS_METHOD')


class Class(StructuredNode):
    name = StringProperty(unique_index=True)
    has_fields = RelationshipTo(Field, 'HAS_FIELD')
    has_methods = RelationshipTo(Method, 'HAS_METHOD')

# === Helper Functions ===

def extract_method_code(content, start_line):
    lines = content.splitlines()
    method_lines = lines[start_line - 1:]

    code_lines = []
    open_braces = 0
    started = False

    for line in method_lines:
        stripped = line.strip()

        # Look for the start of the method body
        if not started:
            if '{' in stripped:
                open_braces += stripped.count('{')
                open_braces -= stripped.count('}')
                code_lines.append(line)
                started = True
            continue
        else:
            open_braces += stripped.count('{')
            open_braces -= stripped.count('}')
            code_lines.append(line)

            if open_braces == 0:
                break

    return "\n".join(code_lines)

def extract_method_signature(method):
    return_type = method.return_type.name if method.return_type else "void"

    visibility = next((m for m in method.modifiers if m in ("public", "private", "protected")), "package-private")

    params = []
    for param in method.parameters:
        param_type = param.type.name if hasattr(param.type, 'name') else str(param.type)
        params.append(f"{param_type} {param.name}")
    parameters_str = ", ".join(params)

    return return_type, visibility, parameters_str

# === Main Parser ===

def parse_java_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    try:
        tree = javalang.parse.parse(content)
        return tree, content
    except:
        return None, None

def build_knowledge_graph(repo_path,exclusions):
    method_map = {}   # method_name -> Method node
    class_map = {}    # class_name -> Class node
    method_by_class = {}  # class_name -> {method_name: Method}
    fields_by_class = {}  # class_name -> {field_name: type}

    # First pass: parse classes, fields, and methods
    for root, _, files in os.walk(repo_path):
        for file in files:
            lowerDir = root.lower()
            if file.endswith('.java'):
                full_path = os.path.join(root, file)
                tree, content = parse_java_file(full_path)
                if not tree:
                    continue
                for _, package_ast in tree.filter(javalang.tree.PackageDeclaration):
                    if package_ast.name in exclusions:
                        print(f'Package {package_ast.name} excluded from knowledge graph')
                        continue
                    else:
                        for _, class_node_ast in tree.filter(javalang.tree.ClassDeclaration):
                            class_name = class_node_ast.name
                            if package_ast.name+"."+class_name in exclusions:
                                print(f'Class {package_ast.name}.{class_name} excluded from knowledge graph')
                                continue
                            class_node = Class.nodes.get_or_none(name=class_name)
                            if not class_node:
                                class_node = Class(name=class_name).save()
                            class_map[class_name] = class_node

                            field_type_map = {}
                            method_node_map = {}

                            # Fields
                            for field in class_node_ast.fields:
                                for decl in field.declarators:
                                    field_name = decl.name
                                    field_type = field.type.name if hasattr(field.type, 'name') else str(field.type)
                                    field_type_map[field_name] = field_type

                                    field_node = Field.nodes.get_or_none(name=field_name)
                                    if not field_node:
                                        field_node = Field(name=field_name, type=field_type).save()
                                    class_node.has_fields.connect(field_node)

                            fields_by_class[class_name] = field_type_map

                            # Methods
                            for method in class_node_ast.methods:
                                method_name = method.name
                                method_start = method.position.line if method.position else 1
                                method_code = extract_method_code(content, method_start)
                                return_type, visibility, parameters = extract_method_signature(method)

                                method_node = Method.nodes.get_or_none(name=method_name)
                                if not method_node:
                                    method_node = Method(
                                        name=method_name,
                                        code=method_code,
                                        return_type=return_type,
                                        visibility=visibility,
                                        parameters=parameters
                                    ).save()
                                class_node.has_methods.connect(method_node)

                                method_map[method_name] = method_node
                                method_node_map[method_name] = method_node

                            method_by_class[class_name] = method_node_map

    # Second pass: build CALLS_METHOD relationships (including inter-class)
    for class_name, methods in method_by_class.items():
        for method_name, method_node in methods.items():
            class_node = class_map[class_name]
            field_type_map = fields_by_class[class_name]

            tree, content = None, ""
            # Find file again (inefficient but simple)
            for root, _, files in os.walk(repo_path):
                for file in files:
                    if file.endswith(".java") and class_name in file:
                        full_path = os.path.join(root, file)
                        tree, content = parse_java_file(full_path)
                        break

            if not tree:
                continue

            for _, class_ast in tree.filter(javalang.tree.ClassDeclaration):
                if class_ast.name != class_name:
                    continue

                for method in class_ast.methods:
                    if method.name != method_name or not method.body:
                        continue

                    for _, call in method.filter(javalang.tree.MethodInvocation):
                        called_method_name = call.member
                        qualifier = call.qualifier

                        callee_node = None

                        # Case 1: qualified call like obj.method()
                        if qualifier:
                            target_class = field_type_map.get(qualifier)
                            if target_class:
                                target_methods = method_by_class.get(target_class, {})
                                callee_node = target_methods.get(called_method_name)

                        # Case 2: unqualified method call
                        if not qualifier and called_method_name in method_map:
                            callee_node = method_map[called_method_name]

                        if callee_node and callee_node != method_node:
                            method_node.calls.connect(callee_node)

if __name__ == "__main__":
    #usage
    #knowledge_graph_builder.py --repo D:\Hemant-Projects\sample-app-for-doc-updater --exclude com.dto com.controller
    parser = argparse.ArgumentParser(description="Process some arguments.")
    parser.add_argument("--repo", type=str, help="Full repository path to build knowledge graph")
    parser.add_argument("--exclude", nargs="+", type=str, help="Packages to exclude")
    args = parser.parse_args()
    #java_repo_path = ""  # 🔁 Replace with your repo path
    clear_existing_graph()
    exclusions = []
    if args.exclude:
        exclusions.extend(args.exclude)
    build_knowledge_graph(args.repo,exclusions)
    print("✅ Knowledge graph built successfully.")
