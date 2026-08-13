class HttpMapbiomasAlertsHook:
    """Cliente GraphQL para a API MapBiomas Alerta v2.

    Autentica via ``signIn`` e consulta imóvel rural e alertas cruzados
    a partir do código CAR.
    """

    GRAPHQL_URL = "https://plataforma.alerta.mapbiomas.org/api/v2/graphql"

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
        import requests

        self.username = username
        self.password = password
        self.url = self.GRAPHQL_URL
        self.session = requests.Session()
        self._token = None

        super().__init__()

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
        headers = {"Content-Type": "application/json"}
        if authenticated:
            token = self._ensure_token()
            headers["Authorization"] = f"Bearer {token}"

        response = self.session.post(
            self.url,
            json={"query": query, "variables": variables or {}},
            headers=headers,
            timeout=120,
        )
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
