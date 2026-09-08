import threading
import time


class HttpMapbiomasAlertsHook:
    """Cliente GraphQL para a API MapBiomas Alerta v2.

    Autentica via ``signIn`` e consulta imóvel rural e alertas cruzados
    a partir do código CAR.
    """

    GRAPHQL_URL = "https://plataforma.alerta.mapbiomas.org/api/v2/graphql"
    TIMEOUT = 120
    MAX_RETRIES = 5
    RETRYABLE_STATUS_CODES = {429, 502, 503, 504}

    SIGN_IN_MUTATION = """
    mutation signIn($email: String!, $password: String!) {
      signIn(email: $email, password: $password) {
        token
      }
    }
    """

    RURAL_PROPERTY_QUERY = """
    query ruralProperty($carCode: String!) {
      ruralProperty(carCode: $carCode) {
        propertyCode
        carType
        areaHa
        state
        stateAcronym
        version
        carUpdatedAt
        insertedAt
        boundingBox
        alerts {
          alertCode
          areaHa
          detectedAt
          publishedAt
          sources
          statusName
          boundingBox {
            neLat
            neLng
            swLat
            swLng
          }
          coordenates {
            latitude
            longitude
          }
          imageAcquiredBeforeAt
          imageAcquiredAfterAt
          publishedImages {
            url
            acquiredAt
            satellite
          }
        }
      }
    }
    """

    def __init__(self, username: str, password: str):
        """Inicializa a sessão HTTP e as credenciais MapBiomas.

        Args:
            username: E-mail da conta MapBiomas Alerta.
            password: Senha da conta MapBiomas Alerta.
        """
        self.username = username
        self.password = password
        self.url = self.GRAPHQL_URL
        self._local = threading.local()
        self._token_lock = threading.Lock()
        self._token = None

        super().__init__()

    @property
    def session(self):
        """Session HTTP isolada por thread."""
        import requests

        session = getattr(self._local, "session", None)
        if session is None:
            session = requests.Session()
            self._local.session = session
        return session

    def _backoff_seconds(self, attempt: int, response=None) -> float:
        """Calcula o tempo de espera entre retries.

        Args:
            attempt: Número da tentativa que acabou de falhar (1-based).
            response: Resposta HTTP, quando houver, para ler ``Retry-After``.

        Returns:
            Segundos de espera, limitados a 60.
        """
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return min(60.0, float(retry_after))
                except ValueError:
                    pass
        return min(60.0, float(2 ** attempt))

    def _sign_in(self) -> str:
        """Autentica na API e obtém o Bearer token.

        Returns:
            Token de autenticação retornado pela mutation ``signIn``.

        Raises:
            RuntimeError: Se a autenticação falhar ou o token não vier
                na resposta.
        """
        payload = self._post_graphql(
            query=self.SIGN_IN_MUTATION,
            variables={"email": self.username, "password": self.password},
            authenticated=False,
        )
        token = (payload.get("data") or {}).get("signIn", {}).get("token")
        if not token:
            raise RuntimeError("Falha na autenticação MapBiomas Alerta: token ausente.")
        self._token = token
        return token

    def _ensure_token(self) -> str:
        """Garante que exista um token válido na sessão.

        Returns:
            Bearer token pronto para uso no header Authorization.
        """
        if self._token:
            return self._token
        with self._token_lock:
            if not self._token:
                return self._sign_in()
            return self._token

    def _post_graphql(
        self,
        query: str,
        variables=None,
        authenticated: bool = True,
    ) -> dict:
        """Envia uma requisição GraphQL para o endpoint MapBiomas.

        Args:
            query: Documento GraphQL (query ou mutation).
            variables: Variáveis da operação GraphQL.
            authenticated: Se ``True``, inclui o Bearer token no header.

        Returns:
            Corpo JSON da resposta GraphQL.

        Raises:
            RuntimeError: Em falha HTTP ou erros GraphQL no body.
        """
        from requests.exceptions import ConnectionError, Timeout

        headers = {"Content-Type": "application/json"}
        if authenticated:
            token = self._ensure_token()
            headers["Authorization"] = f"Bearer {token}"

        last_error = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = self.session.post(
                    self.url,
                    json={"query": query, "variables": variables or {}},
                    headers=headers,
                    timeout=self.TIMEOUT,
                )
            except (Timeout, ConnectionError) as exc:
                last_error = exc
                if attempt == self.MAX_RETRIES:
                    raise RuntimeError(
                        f"Timeout/conexão MapBiomas Alerta após {self.MAX_RETRIES} tentativas: {exc}"
                    ) from exc
                time.sleep(self._backoff_seconds(attempt))
                continue

            if response.status_code in self.RETRYABLE_STATUS_CODES:
                last_error = RuntimeError(
                    f"Erro HTTP MapBiomas Alerta ({response.status_code}): {response.text}"
                )
                if attempt == self.MAX_RETRIES:
                    raise last_error
                time.sleep(self._backoff_seconds(attempt, response))
                continue

            if response.status_code != 200:
                raise RuntimeError(
                    f"Erro HTTP MapBiomas Alerta ({response.status_code}): {response.text}"
                )

            payload = response.json()
            errors = payload.get("errors")
            if errors:
                messages = "; ".join(
                    error.get("message", str(error)) for error in errors
                )
                raise RuntimeError(f"Erro GraphQL MapBiomas Alerta: {messages}")

            return payload

        raise RuntimeError(
            f"Falha MapBiomas Alerta após {self.MAX_RETRIES} tentativas: {last_error}"
        )

    def _graphql(self, query: str, variables=None) -> dict:
        """Executa uma operação GraphQL autenticada.

        Args:
            query: Documento GraphQL.
            variables: Variáveis da operação.

        Returns:
            Campo ``data`` da resposta GraphQL.
        """
        payload = self._post_graphql(query=query, variables=variables, authenticated=True)
        return payload.get("data") or {}

    def get_alerts_by_car(self, car_code: str) -> dict:
        """Busca imóvel rural e alertas cruzados pelo código CAR.

        Args:
            car_code: Código do imóvel no CAR (ex.:
                ``UF-XXXXXXX-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX``).

        Returns:
            Dicionário com ``property`` (dados do imóvel sem a lista de
            alertas) e ``alerts`` (lista de alertas vinculados). Quando o
            CAR não possui cruzamento na base, retorna
            ``{"property": None, "alerts": []}``.
        """
        data = self._graphql(
            query=self.RURAL_PROPERTY_QUERY,
            variables={"carCode": car_code.strip()},
        )
        rural_property = data.get("ruralProperty")
        if not rural_property:
            return {"property": None, "alerts": []}

        alerts = rural_property.pop("alerts", None) or []
        return {"property": rural_property, "alerts": alerts}
