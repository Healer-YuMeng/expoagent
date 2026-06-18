from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .lead_processor import process_and_update_leads

scheduler = AsyncIOScheduler()

# Schedule the job to run every 1 minute
scheduler.add_job(process_and_update_leads, 'interval', minutes=1)
