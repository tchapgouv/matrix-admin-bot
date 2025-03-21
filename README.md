# Matrix Admin Bot

Matrix Admin Bot is a command-line bot for Matrix server administration tasks.

## Currently available commands

- `!server_notice` - Send server notices to users
- `!reset_password` - Reset user passwords
- `!deactivate` - Deactivate user accounts
- `!account_validity` - Manage account validity periods (needs [`email_account_validity` module](https://github.com/tchapgouv/synapse-email-account-validity))

## Configuration

The bot is configured using a TOML file (`config.toml`). Here's an explanation of the available configuration options:

### Basic Configuration

```toml
homeserver = "http://127.0.0.1:8008"    # Matrix homeserver URL
identity_server = "http://127.0.0.1"     # Identity server URL
bot_username = "admin"                   # Bot username
bot_password = "***"                     # Bot password

# Set to true for the primary bot instance
# Set to false for secondary instances if you have multiple bots in one admin room
is_coordinator = true

# List of room IDs where the bot is allowed to operate
# If no rooms is specified, any room can be used
allowed_room_ids = [
  "!tBprUmUcgXAdErtpA:example.org",
]
```

### Two-Factor Authentication

The bot uses TOTP (Time-based One-Time Password) for secure authentication.
You need to specify a TOTP seed per user. Only users with a TOTP defined are
allowed to use the bot.


```toml
[totps]
"@john:example.org" = "AAAAAAAABBBBBBBBCCCCCCCCDDDDDDDD"
"@jack:example.org" = "EEEEEEEEFFFFFFFFGGGGGGGGHHHHHHHH"
```

### Role-Based Access Control

Configure user roles to control access to commands:

```toml
# If no roles are defined, all users defined in `totps` have access to all commands

# Admin role with access to all commands
[roles.admin]
all_commands = true
user_ids = ["@john:example.org"]

# Limited role with access to specific commands only
[roles.resetpwdonly]
allowed_commands = ["ResetPasswordCommand"]
user_ids = ["@jack:example.org"]
```

## Docker Deployment

The bot is available as a Docker image at `ghcr.io/tchapgouv/matrix-admin-bot`.

### Running with Docker

```bash
docker run --rm --name matrix-admin-bot \
           --mount type=bind,src="/path/to/data/folder",dst="/data" \
           --network=host \
           ghcr.io/tchapgouv/matrix-admin-bot:latest
```

Notes:
- Mount your local configuration directory to `/data` inside the container
- The container expects `config.toml` to be in the mounted `/data` directory
- Use `--network=host` when your configuration references `localhost` or `127.0.0.1`
- For production use, consider setting a specific version tag instead of `latest`

## Usage

Once the bot is running and joined to an authorized room:

1. Invoke a command with the proper syntax (e.g., `!server_notice`)
2. Follow the interactive prompts to complete the action
3. Authenticate with your TOTP code when requested

For detailed command help, use the `help` parameter (e.g., `!server_notice help`)
