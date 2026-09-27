# Cognito proves identity; PostgreSQL decides authorization (ADR 0003). Nothing
# here creates a group, a role or a study grant, and nothing in AIA reads one.
#
# The pool admits no self-registration: an administrator provisions each user,
# and the develop seed provisions the operator. Sign-in is Google Workspace only,
# through the hosted UI, Authorization Code + PKCE, no client secret.

resource "aws_cognito_user_pool" "develop" {
  name = "aia-develop"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  deletion_protection      = "INACTIVE" # synthetic users only; destroyed with the environment
  mfa_configuration        = "OFF"      # Google Workspace enforces its own second factor

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  # Federated users never hold a Cognito password, but the pool requires a policy.
  password_policy {
    minimum_length                   = 16
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 1
  }

  schema {
    name                = "email"
    attribute_data_type = "String"
    required            = true
    mutable             = true
    string_attribute_constraints {
      min_length = 3
      max_length = 320
    }
  }

  user_attribute_update_settings {
    attributes_require_verification_before_update = ["email"]
  }
}

resource "aws_cognito_identity_provider" "google" {
  user_pool_id  = aws_cognito_user_pool.develop.id
  provider_name = "Google"
  provider_type = "Google"

  provider_details = {
    client_id        = var.google_client_id
    client_secret    = var.google_client_secret
    authorize_scopes = "openid email profile"
    # Google's `hd` hint restricts the account chooser to the Workspace domain.
    # It is a hint, not a control: the control is that Cognito admits only
    # provisioned users and AIA grants nothing to an unknown one.
    authorize_url                 = "https://accounts.google.com/o/oauth2/v2/auth?hd=${var.google_hosted_domain}"
    attributes_url_add_attributes = "true"
  }

  # `sub` is Google's immutable subject; AIA binds users on Cognito's `sub`
  # first and email second, so an email change keeps the same user (ADR 0003).
  attribute_mapping = {
    username = "sub"
    email    = "email"
    name     = "name"
  }
}

resource "aws_cognito_user_pool_domain" "develop" {
  domain       = var.cognito_domain_prefix
  user_pool_id = aws_cognito_user_pool.develop.id
}

resource "aws_cognito_user_pool_client" "web" {
  name         = "aia-web"
  user_pool_id = aws_cognito_user_pool.develop.id

  # A public client: the browser holds no secret, so PKCE is the proof.
  generate_secret                      = false
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = [aws_cognito_identity_provider.google.provider_name]
  explicit_auth_flows                  = ["ALLOW_REFRESH_TOKEN_AUTH"]

  callback_urls = ["https://${var.public_hostname}/auth/callback"]
  logout_urls   = ["https://${var.public_hostname}/"]

  # The API verifies the id token (AIA_COGNITO_TOKEN_USE=id). One hour is the
  # ceiling; the client refreshes silently with the refresh token.
  id_token_validity      = 60
  access_token_validity  = 60
  refresh_token_validity = 30
  token_validity_units {
    id_token      = "minutes"
    access_token  = "minutes"
    refresh_token = "days"
  }

  prevent_user_existence_errors = "ENABLED"
  enable_token_revocation       = true

  depends_on = [aws_cognito_identity_provider.google]
}
