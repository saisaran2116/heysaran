import { MongoClient, ObjectId } from 'mongodb'
import pg from 'pg'
import { createClient } from 'redis'
import { drizzle } from 'drizzle-orm/node-postgres'
import { pgTable, uuid, text, timestamp } from 'drizzle-orm/pg-core'
import { readFile } from 'node:fs/promises'

export const users = pgTable('accounts', {
  id: uuid().primaryKey().defaultRandom(), email: text().notNull().unique(),
  password: text(), googleSub: text('google_sub').unique(), role: text().notNull().default('member'),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow(),
})

export async function connect(env) {
  const pool = new pg.Pool({ connectionString: env.DATABASE_URL })
  const mongo = new MongoClient(env.MONGO_URL)
  const redis = createClient({ url: env.REDIS_URL })
  redis.on('error', error => console.error('Redis', error.message))
  try {
    await Promise.all([mongo.connect(), redis.connect()])
    await pool.query(await readFile(new URL('./schema.sql', import.meta.url), 'utf8'))
    const db = mongo.db('heybaby')
    const library = db.collection('library')
    await library.createIndex({ owner: 1, kind: 1, updatedAt: -1 })
    return { pool, orm: drizzle(pool), library, redis, close: () => Promise.all([pool.end(), mongo.close(), redis.quit()]) }
  } catch (error) {
    await Promise.allSettled([pool.end(), mongo.close(), redis.isOpen && redis.destroy()])
    throw error
  }
}

export function ownedId(owner, id) {
  return { owner, _id: ObjectId.createFromHexString(id) }
}
