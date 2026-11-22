import { randomBytes, scrypt as derive, timingSafeEqual } from 'node:crypto'
import { promisify } from 'node:util'
import { SignJWT, jwtVerify } from 'jose'

const scrypt = promisify(derive)
export async function hash(password) {
  const salt = randomBytes(16).toString('hex')
  return salt + ':' + (await scrypt(password, salt, 64)).toString('hex')
}
export async function matches(password, stored) {
  if (!stored) return false
  const [salt, digest] = stored.split(':')
  const expected = Buffer.from(digest, 'hex')
  return timingSafeEqual(expected, await scrypt(password, salt, expected.length))
}

export function sessions(secret) {
  const key = new TextEncoder().encode(secret)
  const options = { issuer: 'heybaby-studio', audience: 'studio', algorithms: ['HS256'] }
  function cookie(req, name) {
    return req.headers.cookie?.split('; ').find(value => value.startsWith(name + '='))?.slice(name.length + 1)
  }
  return {
    cookie,
    issue: id => new SignJWT().setProtectedHeader({ alg: 'HS256' }).setSubject(id)
      .setIssuer(options.issuer).setAudience(options.audience).setExpirationTime('8h').sign(key),
    async read(req) {
      try { return (await jwtVerify(cookie(req, 'hb_session'), key, options)).payload.sub }
      catch { return undefined }
    }
  }
}
