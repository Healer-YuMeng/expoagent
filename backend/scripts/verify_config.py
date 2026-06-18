#!/usr/bin/env python3
"""
验证配置是否正确的工具脚本

用法:
    python backend/scripts/verify_config.py
"""
import sys
import os
import subprocess
from pathlib import Path


def get_env_paths():
    project_root = Path(".")
    return project_root / ".env", project_root / ".env.example"


def check_env_file():
    """检查 .env 文件是否存在"""
    print("=" * 70)
    print("1. 检查 .env 文件")
    print("-" * 70)
    
    env_path, env_example_path = get_env_paths()
    
    if env_example_path.exists():
        print("✅ .env.example 文件存在")
    else:
        print("❌ .env.example 文件不存在")
        return False
    
    if env_path.exists():
        print(f"✅ 根目录 .env 文件存在: {env_path}")
        return True
    else:
        print("❌ .env 文件不存在")
        print("\n💡 解决方案:")
        print(f"   cp {env_example_path} {env_path}")
        return False


def check_required_vars():
    """检查必需的环境变量"""
    print("\n" + "=" * 70)
    print("2. 检查必需的环境变量")
    print("-" * 70)
    
    # 添加 backend 目录到 Python 路径
    backend_path = Path(__file__).parent.parent
    sys.path.insert(0, str(backend_path))
    
    try:
        from app.core.config import settings
        
        required_vars = {
            "POSTGRES_URL": settings.POSTGRES_URL,
            "SECRET_KEY": settings.SECRET_KEY,
        }
        provider = settings.LLM_PROVIDER.lower()
        if provider == "openai":
            required_vars["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
        elif provider == "qwen":
            required_vars["QWEN_API_KEY"] = settings.QWEN_API_KEY
        
        all_good = True
        
        for var_name, var_value in required_vars.items():
            if not var_value:
                print(f"❌ {var_name} 未设置")
                all_good = False
            elif var_name == "SECRET_KEY":
                if var_value == "your-secret-key-please-change-me-use-openssl-rand-hex-32":
                    print(f"⚠️  {var_name} 使用默认值（不安全）")
                    print("   💡 运行: python backend/scripts/generate_secret_key.py")
                    all_good = False
                elif len(var_value) < 32:
                    print(f"⚠️  {var_name} 长度过短（建议至少 32 字符）")
                    all_good = False
                else:
                    print(f"✅ {var_name} 已设置（长度: {len(var_value)}）")
            elif var_name == "OPENAI_API_KEY":
                if not var_value:
                    print("❌ OPENAI_API_KEY 未设置")
                    all_good = False
                else:
                    print("✅ OPENAI_API_KEY 已设置")
            elif var_name == "POSTGRES_URL":
                print(f"✅ {var_name} 已设置")
            elif var_name == "QWEN_API_KEY":
                if not var_value:
                    print("❌ QWEN_API_KEY 未设置")
                    all_good = False
                else:
                    print("✅ QWEN_API_KEY 已设置")
            else:
                print(f"✅ {var_name} 已设置")
        
        return all_good
        
    except Exception as e:
        print(f"❌ 加载配置失败: {str(e)}")
        return False


def check_postgres_connection():
    """检查 PostgreSQL 连接"""
    print("\n" + "=" * 70)
    print("3. 检查 PostgreSQL 连接")
    print("-" * 70)
    
    # 检查 Docker 容器
    import subprocess
    
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=General_ageng_postgres", "--format", "{{.Status}}"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0 and result.stdout.strip():
            print(f"✅ PostgreSQL 容器运行中: {result.stdout.strip()}")
        else:
            print("❌ PostgreSQL 容器未运行")
            print("\n💡 解决方案:")
            print("   docker compose up -d")
            return False
            
    except FileNotFoundError:
        print("⚠️  Docker 未安装或不在 PATH 中")
        return False
    
    # 测试连接
    try:
        backend_path = Path(__file__).parent.parent
        sys.path.insert(0, str(backend_path))
        
        import asyncpg
        from app.core.config import settings
        import asyncio

        async def test_connection():
            try:
                conn = await asyncpg.connect(settings.POSTGRES_URL)
                await conn.execute("SELECT 1")
                print("✅ PostgreSQL 连接成功")
                await conn.close()
                return True
            except Exception as e:
                print(f"❌ PostgreSQL 连接失败: {str(e)}")
                return False
        
        return asyncio.run(test_connection())
        
    except Exception as e:
        print(f"❌ 测试连接时出错: {str(e)}")
        return False


def check_gitignore():
    """检查 .gitignore 配置"""
    print("\n" + "=" * 70)
    print("4. 检查 .gitignore 配置")
    print("-" * 70)
    
    gitignore_path = Path(".gitignore")
    
    if not gitignore_path.exists():
        print("❌ .gitignore 文件不存在")
        return False
    
    with open(gitignore_path, 'r') as f:
        content = f.read()
    
    checks = {
        ".env": ".env" in content,
        "logs": "logs/" in content or "*.log" in content,
        "__pycache__": "__pycache__/" in content,
    }
    
    all_good = True
    for item, exists in checks.items():
        if exists:
            print(f"✅ {item} 已被忽略")
        else:
            print(f"❌ {item} 未被忽略")
            all_good = False
    
    env_path, _ = get_env_paths()

    # 检查 .env 是否被 Git 跟踪
    try:
        tracked = []
        result = subprocess.run(
            ["git", "ls-files", str(env_path)],
            capture_output=True,
            text=True
        )
        if result.stdout.strip():
            tracked.append(str(env_path))

        if tracked:
            print(f"⚠️  以下 .env 文件被 Git 跟踪（应该被忽略）: {', '.join(tracked)}")
            print("\n💡 解决方案:")
            for env_path in tracked:
                print(f"   git rm --cached {env_path}")
            print("   git commit -m 'Remove .env from tracking'")
            all_good = False
        else:
            print("✅ .env 文件未被 Git 跟踪")
            
    except FileNotFoundError:
        print("⚠️  Git 未安装或不在 PATH 中")
    
    return all_good


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("YCIS 招生系统 - 配置验证工具")
    print("=" * 70)
    
    # 切换到项目根目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    os.chdir(project_root)
    
    print(f"\n📁 项目目录: {project_root}")
    
    # 执行检查
    results = []
    
    results.append(("环境文件", check_env_file()))
    results.append(("环境变量", check_required_vars()))
    results.append(("PostgreSQL连接", check_postgres_connection()))
    results.append(("Git配置", check_gitignore()))
    
    # 输出总结
    print("\n" + "=" * 70)
    print("📊 检查结果汇总")
    print("=" * 70)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name:.<20} {status}")
    
    all_passed = all(result for _, result in results)
    
    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 所有检查通过！系统配置正确。")
        print("\n下一步:")
        print("  1. 启动后端: cd backend && uvicorn app.main:app --reload")
        print("  2. 启动前端: cd frontend && npm run dev")
        print("  3. 访问: http://localhost:8006")
    else:
        print("⚠️  部分检查未通过，请根据上述提示修复。")
        print("\n参考文档:")
        print("  - README.md - 项目快速启动说明")
        print("  - .env.example - 环境变量模板")
    print("=" * 70 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n❌ 操作已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
