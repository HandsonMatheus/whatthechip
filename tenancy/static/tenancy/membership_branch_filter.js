/* Vínculo (Membership) no Django admin: filtra o select de FILIAL pela EMPRESA
 * escolhida. As <option> chegam com data-company (widget BranchSelect em
 * tenancy/admin.py); aqui só reconstruímos a lista quando a empresa muda.
 * Sem empresa selecionada → mostra todas (o portão do modelo barra mismatch
 * de qualquer jeito — isto é UX, não segurança). */
'use strict';
{
  function init() {
    const company = document.getElementById('id_company');
    const branch  = document.getElementById('id_branch');
    if (!company || !branch) return;

    // Snapshot de todas as opções na carga (vazia = "---------").
    const all = Array.from(branch.options).map(function (o) {
      return { value: o.value, text: o.text, company: o.dataset.company || '' };
    });

    function rebuild() {
      const cid = company.value;
      const current = branch.value;
      branch.innerHTML = '';
      all.forEach(function (o) {
        if (o.value === '' || !cid || o.company === cid) {
          branch.add(new Option(o.text, o.value));
        }
      });
      // Preserva a seleção se ela ainda é válida; senão volta ao vazio.
      const stillThere = Array.from(branch.options).some(function (o) {
        return o.value === current;
      });
      branch.value = stillThere ? current : '';
    }

    company.addEventListener('change', rebuild);
    rebuild(); // filtra já na carga (form de edição vem com empresa preenchida)
  }

  if (document.readyState !== 'loading') init();
  else document.addEventListener('DOMContentLoaded', init);
}
