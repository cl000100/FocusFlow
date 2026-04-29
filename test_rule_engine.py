from core import RuleEngine

# 测试规则提取
print("测试规则提取功能")
print("-" * 50)

# 测试从应用名称提取规则
app_name = "aaa-test-新建页面-Trae CN"
app_rules = RuleEngine.extract_rules_from_app_name(app_name)
print(f"从应用名称 '{app_name}' 提取的规则:")
for rule in app_rules:
    print(f"  - {rule}")

# 测试从文件路径提取规则
file_path = "app_detector.py - FocusFlow - Trae CN"
file_rules = RuleEngine.extract_rules_from_file_path(file_path)
print(f"\n从文件路径 '{file_path}' 提取的规则:")
for rule in file_rules:
    print(f"  - {rule}")

# 测试规则匹配
print("\n测试规则匹配功能")
print("-" * 50)

# 测试文件名匹配
rule = "app_detector"
target = "app_detector.py"
result = RuleEngine.match_rule(rule, target, "file_name")
print(f"文件名匹配: '{rule}' 在 '{target}' 中 -> {result}")

# 测试应用名匹配
rule = "Trae"
target = "Trae CN"
result = RuleEngine.match_rule(rule, target, "app_name")
print(f"应用名匹配: '{rule}' 在 '{target}' 中 -> {result}")

# 测试文件路径匹配
rule = "FocusFlow"
target = "app_detector.py - FocusFlow - Trae CN"
result = RuleEngine.match_rule(rule, target, "file_path")
print(f"文件路径匹配: '{rule}' 在 '{target}' 中 -> {result}")

# 测试组合匹配
rule = "app:Trae,file:FocusFlow"
target = {"app_name": "Trae CN", "file_path": "app_detector.py - FocusFlow - Trae CN"}
result = RuleEngine.match_rule(rule, target, "combination")
print(f"组合匹配: '{rule}' 匹配 '{target}' -> {result}")

# 测试获取匹配文件
print("\n测试获取匹配文件功能")
print("-" * 50)

# 测试获取匹配文件
matching_files = RuleEngine.get_matching_files("Trae", "app_name", limit=5)
print(f"匹配应用名 'Trae' 的文件:")
for file_info in matching_files:
    print(f"  - {file_info['file_path']} (应用: {file_info['app_name']})")

print("\n测试完成！")
