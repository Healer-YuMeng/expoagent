#!/usr/bin/env python3
"""
数据库初始化脚本

功能：
1. 创建所有必要的索引
2. 创建默认管理员账号
3. 验证数据库连接

使用方法：
    python scripts/init_db.py

选项：
    --reset: 重置数据库（删除所有数据，仅在 DEBUG 模式下可用）
"""
import asyncio
import sys
import argparse
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db import (
    connect_to_postgres,
    close_postgres_connection,
    init_db_indexes,
    create_default_teacher,
    drop_all_collections,
    get_database
)
from app.core.config import settings
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_connection():
    """测试数据库连接"""
    try:
        logger.info("🔍 测试数据库连接...")
        database = get_database()
        
        # 尝试执行一个简单的操作
        await database.command("ping")
        
        logger.info("✅ 数据库连接正常")
        return True
    except Exception as e:
        logger.error(f"❌ 数据库连接失败: {str(e)}")
        return False


async def init_database(reset: bool = False):
    """初始化数据库"""
    try:
        logger.info("=" * 60)
        logger.info("🚀 开始初始化 YCIS 招生系统数据库")
        logger.info("=" * 60)
        
        # 显示配置信息
        logger.info(f"\n📋 配置信息:")
        logger.info(f"   PostgreSQL URL: {settings.POSTGRES_URL}")
        logger.info(f"   数据库名称: {settings.DB_NAME}")
        logger.info(f"   DEBUG 模式: {settings.DEBUG}")
        logger.info(f"   意向评分阈值: {settings.INTENT_SCORE_THRESHOLD}")
        
        # 连接数据库
        logger.info("\n🔌 连接到数据库...")
        await connect_to_postgres()
        
        # 测试连接
        if not await test_connection():
            raise Exception("数据库连接测试失败")
        
        # 如果需要重置
        if reset:
            logger.info("\n⚠️  警告: 即将重置数据库（删除所有数据）")
            if not settings.DEBUG:
                logger.error("❌ 重置操作仅允许在 DEBUG 模式下执行！")
                return False
            
            # 等待确认
            logger.info("此操作将删除所有数据，是否继续？")
            logger.info("如需继续，请在 5 秒内不要中断程序...")
            await asyncio.sleep(5)
            
            await drop_all_collections()
        
        # 创建索引
        logger.info("\n📊 创建数据库索引...")
        await init_db_indexes()
        
        # 创建默认教师
        logger.info("\n👤 创建默认教师账号...")
        await create_default_teacher()
        
        # 显示统计信息
        logger.info("\n📈 数据库统计:")
        database = get_database()
        
        collections = ["users", "conversations", "messages", "leads"]
        for collection_name in collections:
            count = await database[collection_name].count_documents({})
            logger.info(f"   {collection_name}: {count} 条记录")
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ 数据库初始化完成！")
        logger.info("=" * 60)
        
        if reset:
            logger.info("\n⚠️  默认教师账号:")
            logger.info("   📱 手机号: 13800138001")
            logger.info("   🔒 密码: teacher123456")
            logger.info("   ⚠️  请立即修改密码！")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ 初始化失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    finally:
        # 关闭连接
        await close_postgres_connection()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='YCIS 招生系统数据库初始化脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 初始化数据库（创建索引和默认管理员）
  python scripts/init_db.py
  
  # 重置数据库（删除所有数据并重新初始化）
  python scripts/init_db.py --reset
        """
    )
    
    parser.add_argument(
        '--reset',
        action='store_true',
        help='重置数据库（删除所有数据，仅在 DEBUG 模式下可用）'
    )
    
    args = parser.parse_args()
    
    # 运行初始化
    success = asyncio.run(init_database(reset=args.reset))
    
    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
