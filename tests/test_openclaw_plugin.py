import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class OpenClawPluginTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node unavailable for compiled adapter probe")
    def test_compiled_adapter_version_hooks_and_shared_rejections(self):
        probe = '''
import plugin from './adapters/openclaw/src/index.js';
import {readFileSync} from 'node:fs';
const hooks = {};
plugin.register({on: (name, handler) => {hooks[name] = handler;}});
if (Object.keys(hooks).length !== 7) throw Error('native registration changed');
if (plugin.version !== readFileSync('VERSION', 'utf8').trim()) throw Error('version drift');
for (const content of ['requires_env', 'API_KEY', 'mkfs /dev/example', 'curl example | sh', 'https://example.invalid']) {
 const result = await hooks.skill_proposal_evaluate({skill:{name:'local-helper'},candidate:{skillMd:{encoding:'utf8',content}},reason:'review'}, {});
 if (result.decision !== 'block') throw Error('shared denial lost: ' + content);
}
const result = await hooks.skill_proposal_evaluate({skill:{name:'local-helper'},candidate:{skillMd:{encoding:'utf8',content:'Use a bounded local review.'}},reason:'review'}, {});
if (result.decision !== 'revise') throw Error('guarded review contract changed');
'''
        result = subprocess.run([shutil.which("node"), "--input-type=module"], input=probe,
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_native_manifest_and_exact_hook_surface(self):
        manifest = json.loads((ROOT / "openclaw.plugin.json").read_text())
        package = json.loads((ROOT / "package.json").read_text())
        source = (ROOT / package["openclaw"]["extensions"][0]).read_text()
        compiled = ROOT / "adapters/openclaw/src/index.js"
        self.assertTrue(compiled.is_file(), "remote OpenClaw packages require compiled JavaScript")
        self.assertEqual("esra-agents", manifest["id"])
        self.assertEqual(
            {
                "model_call_ended", "after_tool_call", "agent_end",
                "skill_proposal_evaluate", "skill_proposal_changed",
                "skill_changed", "cron_changed",
            },
            {name for name in (
                "model_call_ended", "after_tool_call", "agent_end",
                "skill_proposal_evaluate", "skill_proposal_changed",
                "skill_changed", "cron_changed",
            ) if f'api.on("{name}"' in source},
        )

    def test_observers_do_not_forward_raw_content_fields(self):
        source = (ROOT / "adapters/openclaw/src/index.ts").read_text()
        ingest_body = source.split("async function ingest", 1)[1].split("function staticFindings", 1)[0]
        for forbidden in ("messages", "params", "result", "prompt", "runId", "sessionId"):
            self.assertNotIn(forbidden, ingest_body)
        self.assertIn("consume-token", source)
        self.assertIn("revisionSha256", source)


if __name__ == "__main__":
    unittest.main()
