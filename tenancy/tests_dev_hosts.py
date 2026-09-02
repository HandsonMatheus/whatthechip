"""
Hosts de desenvolvimento — a trava que impede a conveniência de virar buraco.

`dev_hosts_from_env` existe para o celular alcançar o `runserver` na rede
local. A garantia que importa não é ela funcionar: é ela **não** funcionar
fora do DEBUG. Host aceito é superfície de ataque (Host header poisoning), e
uma variável esquecida no painel da Render não pode abrir produção.

Mora em `tenancy` porque é o app dono de hosts e domínios — e porque a suíte
de `core` não roda na rodada normal (`core` não tem testes).
"""

from django.test import SimpleTestCase

from core.settings import dev_hosts_from_env


class ForaDoDebugTests(SimpleTestCase):
    """A única garantia com consequência de segurança."""

    def test_sem_debug_nao_devolve_nada(self):
        self.assertEqual(dev_hosts_from_env('192.168.0.42', debug=False),
                         ([], []))

    def test_sem_debug_ignora_ate_lista_cheia(self):
        """O caso real: alguém deixa a variável setada no Render."""
        self.assertEqual(
            dev_hosts_from_env('10.0.0.1,10.0.0.2:9000', debug=False),
            ([], []))


class ComDebugTests(SimpleTestCase):

    def test_host_simples_vira_allowed_e_csrf_na_8000(self):
        allowed, origins = dev_hosts_from_env('192.168.0.42', debug=True)
        self.assertEqual(allowed, ['192.168.0.42'])
        self.assertEqual(origins, ['http://192.168.0.42:8000'])

    def test_porta_explicita_e_respeitada(self):
        _, origins = dev_hosts_from_env('192.168.0.42:9000', debug=True)
        self.assertEqual(origins, ['http://192.168.0.42:9000'])

    def test_ALLOWED_HOSTS_nunca_leva_porta(self):
        """O Django tira a porta antes de comparar — host com porta aqui
        simplesmente nunca casaria, e o sintoma seria DisallowedHost com a
        variável 'certa' configurada."""
        allowed, _ = dev_hosts_from_env('192.168.0.42:9000', debug=True)
        self.assertEqual(allowed, ['192.168.0.42'])

    def test_varios_separados_por_virgula(self):
        allowed, origins = dev_hosts_from_env(
            ' 192.168.0.42 , 10.0.0.7:3000 ', debug=True)
        self.assertEqual(allowed, ['192.168.0.42', '10.0.0.7'])
        self.assertEqual(origins, ['http://192.168.0.42:8000',
                                   'http://10.0.0.7:3000'])

    def test_vazio_e_lixo_nao_viram_host(self):
        """String vazia, só vírgulas, só espaço: nenhum host fantasma."""
        for valor in ('', '   ', ',,,', ' , '):
            self.assertEqual(dev_hosts_from_env(valor, debug=True), ([], []),
                             f'entrada {valor!r} produziu host')
