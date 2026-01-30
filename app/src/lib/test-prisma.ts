import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

async function test() {
    console.log('Testing Prisma connection...')
    try {
        const userCount = await prisma.user.count()
        console.log('User count:', userCount)
        console.log('Connection successful!')
    } catch (error) {
        console.error('Prisma error:', error)
    } finally {
        await prisma.$disconnect()
    }
}

test()
