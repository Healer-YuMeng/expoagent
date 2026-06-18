#!/usr/bin/env python3
"""
生成随机 SECRET_KEY 的工具脚本

用法:
    python backend/scripts/generate_secret_key.py
"""
import secrets
import sys


def generate_secret_key(length: int = 64) -> str:
    """
    生成随机密钥
    
    Args:
        length: 密钥长度（十六进制字符数，默认64）
        
    Returns:
        str: 随机生成的十六进制密钥
    """
    return secrets.token_hex(length // 2)


def main():
    print("=" * 70)
    print("YCIS 招生系统 - SECRET_KEY 生成工具")
    print("=" * 70)
    print()
    
    # 生成密钥
    secret_key = generate_secret_key(64)
    
    print("✅ 已生成随机 SECRET_KEY:")
    print()
    print(f"  {secret_key}")
    print()
    print("-" * 70)
    print()
    print("📝 使用方法:")
    print()
    print("方法 1: 复制到项目根目录 .env 文件中")
    print(f"  SECRET_KEY={secret_key}")
    print()
    print("方法 2: 通过环境变量设置（Linux/macOS）")
    print(f"  export SECRET_KEY='{secret_key}'")
    print()
    print("方法 3: 通过环境变量设置（Windows）")
    print(f"  set SECRET_KEY={secret_key}")
    print()
    print("-" * 70)
    print()
    print("⚠️  重要提示:")
    print("  1. 请妥善保管此密钥，不要泄露给他人")
    print("  2. 不要将此密钥提交到 Git 仓库")
    print("  3. 生产环境和开发环境应使用不同的密钥")
    print("  4. 如果密钥泄露，请立即重新生成并更新")
    print()
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ 操作已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 错误: {str(e)}")
        sys.exit(1)
