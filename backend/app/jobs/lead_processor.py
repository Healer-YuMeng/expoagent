from ..db import get_database

async def process_and_update_leads():
    """
    精简后的定时任务：仅检查是否存在缺少提取信息的线索并记录日志。
    """
    db = get_database()
    print("Scheduler Job: Checking for new leads to process...")

    count = await db.leads.count_documents({"extracted_info": {"$exists": False}})
    if count > 0:
        print(f"Scheduler Job: {count} leads created without extracted_info.")
