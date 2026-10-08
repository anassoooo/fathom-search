import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

async function main() {
  console.log('Setting up database...')
  
  // The database and tables will be created by Prisma migrate
  // This script can be used for seeding demo data if needed
  
  console.log('Database setup complete!')
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect())
