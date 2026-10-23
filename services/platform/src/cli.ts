import { main } from './administration.js'

main().catch(() => { process.stderr.write('Platform operation failed. Check arguments, existing configuration, migration state and last-admin safeguards. No credentials were printed.\n'); process.exitCode = 1 })
