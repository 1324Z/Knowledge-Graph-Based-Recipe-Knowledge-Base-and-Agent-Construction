import os

def get_dir_size(path):
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except:
                    pass
    except:
        pass
    return total

def format_size(size):
    if size >= 1024**3:
        return f"{size/1024**3:.2f} GB"
    elif size >= 1024**2:
        return f"{size/1024**2:.1f} MB"
    elif size >= 1024:
        return f"{size/1024:.1f} KB"
    else:
        return f"{size} B"

def scan_dir(path, depth=0, max_depth=2):
    items = []
    try:
        entries = sorted(os.listdir(path))
    except:
        return items
    
    for entry in entries:
        full_path = os.path.join(path, entry)
        if os.path.isdir(full_path):
            size = get_dir_size(full_path)
            items.append((depth, entry, size, True))
            if depth < max_depth:
                items.extend(scan_dir(full_path, depth+1, max_depth))
        else:
            try:
                size = os.path.getsize(full_path)
            except:
                size = 0
            items.append((depth, entry, size, False))
    return items

# Scan e:\rag
print("=" * 70)
print("E:\\RAG 项目目录结构")
print("=" * 70)

# Top level
top_items = scan_dir(r"e:\rag", depth=0, max_depth=0)
for depth, name, size, is_dir in top_items:
    prefix = "[D]" if is_dir else "   "
    print(f"  {prefix} {name:<45} {format_size(size):>10}")

print()

# all-in-rag detailed
print("=" * 70)
print("E:\\RAG\\all-in-rag 详细结构")
print("=" * 70)
items = scan_dir(r"e:\rag\all-in-rag", depth=0, max_depth=2)
for depth, name, size, is_dir in items:
    indent = "  " * (depth + 1)
    prefix = "[D]" if is_dir else "   "
    if depth <= 1 or size > 1024*1024:  # Show top 2 levels + large files
        print(f"  {indent}{prefix} {name:<40} {format_size(size):>10}")

print()

# What-to-eat-today detailed
print("=" * 70)
print("E:\\RAG\\What-to-eat-today 详细结构")
print("=" * 70)
items = scan_dir(r"e:\rag\What-to-eat-today", depth=0, max_depth=2)
for depth, name, size, is_dir in items:
    indent = "  " * (depth + 1)
    prefix = "[D]" if is_dir else "   "
    if depth <= 1 or size > 1024*1024:
        print(f"  {indent}{prefix} {name:<40} {format_size(size):>10}")

# Total
print()
print("=" * 70)
all_rag_size = get_dir_size(r"e:\rag\all-in-rag")
wte_size = get_dir_size(r"e:\rag\What-to-eat-today")
models_size = get_dir_size(r"e:\rag\all-in-rag\models")
print(f"all-in-rag 总计:        {format_size(all_rag_size):>10}")
print(f"  - models (嵌入模型):  {format_size(models_size):>10}")
print(f"  - data (数据+Docker): {format_size(all_rag_size - models_size):>10}")
print(f"What-to-eat-today 总计: {format_size(wte_size):>10}")
print(f"  - frontend (前端):    {format_size(get_dir_size(r'e:\rag\What-to-eat-today\frontend\node_modules')):>10} (node_modules)")
print(f" Grand Total:           {format_size(all_rag_size + wte_size):>10}")
