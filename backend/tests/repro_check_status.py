import asyncio, sys
sys.path.insert(0, "/app/backend")
import server

async def main():
    names = ["Vasanth D","Adhya Anil Kumar","Radhakrishnan M","Shridhar S","Sivalingaraja S"]
    for n in names:
        e = await server.db.employees.find_one({"full_name": n}, {"_id":0,"full_name":1,"employee_status":1,"last_day_payable":1,"relieving_date":1,"date_of_relieving":1})
        print(n, "->", {k:v for k,v in (e or {}).items() if k!="full_name"})

asyncio.run(main())
