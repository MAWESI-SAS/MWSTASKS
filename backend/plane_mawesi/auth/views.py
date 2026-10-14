# Copyright (c) 2026-present MAWESI S.A.S.
# SPDX-License-Identifier: AGPL-3.0-only
"""Rutas /auth/microsoft/ y /auth/microsoft/callback/. Mismo flujo que GoogleOauthInitiateEndpoint /
GoogleCallbackEndpoint de Plane (sesión, state, next_path, redirección segura)."""
import uuid

from django.http import HttpResponseRedirect, JsonResponse
from django.views import View

from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES, AuthenticationException
from plane.authentication.utils.host import base_host
from plane.authentication.utils.login import user_login
from plane.authentication.utils.redirection_path import get_redirection_path
from plane.authentication.utils.user_auth_workflow import post_user_auth_workflow
from plane.license.models import Instance
from plane.utils.path_validator import get_safe_redirect_url

from plane_mawesi.auth import microsoft


def _back(request, next_path, exc=None):
    params = exc.get_error_dict() if exc else {}
    return HttpResponseRedirect(get_safe_redirect_url(
        base_url=base_host(request=request, is_app=True), next_path=next_path, params=params))


class MicrosoftInitiateEndpoint(View):
    def get(self, request):
        request.session["host"] = base_host(request=request, is_app=True)
        next_path = request.GET.get("next_path")
        if next_path:
            request.session["next_path"] = str(next_path)
        instance = Instance.objects.first()
        if instance is None or not instance.is_setup_done:
            return _back(request, next_path, AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["INSTANCE_NOT_CONFIGURED"], error_message="INSTANCE_NOT_CONFIGURED"))
        try:
            state = uuid.uuid4().hex
            provider = microsoft.MicrosoftOAuthProvider(request=request, state=state)
            request.session["state"] = state
            return HttpResponseRedirect(provider.get_auth_url())
        except AuthenticationException as e:
            return _back(request, next_path, e)


class MicrosoftCallbackEndpoint(View):
    def get(self, request):
        next_path = request.session.get("next_path")
        state, code = request.GET.get("state"), request.GET.get("code")
        expected = request.session.pop("state", "")
        if not code or not expected or state != expected:
            return _back(request, next_path, AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["AUTHENTICATION_FAILED"], error_message="AUTHENTICATION_FAILED"))
        try:
            provider = microsoft.MicrosoftOAuthProvider(request=request, code=code, callback=post_user_auth_workflow)
            user = provider.authenticate()
            user_login(request=request, user=user, is_app=True)
            path = next_path or get_redirection_path(user=user)
            return HttpResponseRedirect(get_safe_redirect_url(
                base_url=base_host(request=request, is_app=True), next_path=path, params={}))
        except AuthenticationException as e:
            return _back(request, next_path, e)


class AuthProvidersEndpoint(View):
    """Pública: qué logins extra de MWSTASKS están activos (la web decide si muestra el botón)."""

    def get(self, request):
        return JsonResponse({"microsoft": microsoft.is_enabled()})
