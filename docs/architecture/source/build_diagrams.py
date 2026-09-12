"""Rebuild the submission diagrams from editable SVG primitives and official AWS icons."""
from pathlib import Path
from zipfile import ZipFile
from html import escape
import base64
import json

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = HERE.parent if (HERE / 'manifest.json').exists() else ROOT / 'output' / 'architecture'
OUT.mkdir(parents=True, exist_ok=True)
ICONS = OUT / 'source' / 'aws-icons'
ICONS.mkdir(parents=True, exist_ok=True)
ARCHIVE = Path(__file__).parent / 'aws-icons.zip'
PALETTE = {
    'green': ('#eaf5ed', '#6b9c7c'),
    'blue': ('#edf3ff', '#718ec4'),
    'purple': ('#f2ecfb', '#9a7ac5'),
    'amber': ('#fff7e6', '#c89b58'),
    'red': ('#fff0ee', '#c7837b'),
    'gray': ('#f6f8fa', '#a7b1bd'),
}
INK = '#24313f'
MUTED = '#5c6b7a'
SERVICE_NAMES = {
    'cloudfront': 'Amazon-CloudFront', 's3': 'Amazon-Simple-Storage-Service',
    'api': 'Amazon-API-Gateway', 'lambda': 'AWS-Lambda',
    'dynamodb': 'Amazon-DynamoDB', 'sqs': 'Amazon-Simple-Queue-Service',
    'fargate': 'AWS-Fargate', 'agentcore': 'Amazon-Bedrock-AgentCore',
    'bedrock': 'Amazon-Bedrock', 'polly': 'Amazon-Polly',
    'cloudwatch': 'Amazon-CloudWatch', 'eventbridge': 'Amazon-EventBridge',
    'ecr': 'Amazon-Elastic-Container-Registry',
}
if ARCHIVE.exists():
    with ZipFile(ARCHIVE) as archive:
        names = archive.namelist()
        for key, service in SERVICE_NAMES.items():
            match = next(n for n in names if not n.startswith('__MACOSX/') and n.endswith(f'/Arch_{service}_64.svg'))
            (ICONS / f'{key}.svg').write_bytes(archive.read(match))
else:
    assert all((ICONS / f'{key}.svg').exists() for key in SERVICE_NAMES), 'Missing bundled AWS icons'


class Diagram:
    def __init__(self, slug, title, subtitle, width, height, number):
        self.slug, self.width, self.height = slug, width, height
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">',
            f'<title id="title">{escape(title)}</title><desc id="description">{escape(subtitle)}</desc>',
            '<defs>']
        for color in [INK, '#6b9c7c', '#718ec4', '#9a7ac5', '#c89b58', '#c7837b', '#8995a3']:
            ident = color[1:]
            self.parts.append(f'<marker id="arrow{ident}" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto" markerUnits="userSpaceOnUse"><path d="M1 1 L8 5 L1 9" fill="none" stroke="{color}" stroke-width="2"/></marker>')
        self.parts.extend(['</defs>', '<rect width="100%" height="100%" fill="white"/>'])
        self.text(64, 70, title, 38, weight=700)
        self.text(64, 112, subtitle, 21, MUTED)
        self.text(width - 64, 72, f'CITEREEL / {number:02d}', 18, MUTED, anchor='end', weight=600)

    def rect(self, x, y, w, h, fill='white', stroke='#d9e0e6', radius=6, dash=None, sw=2):
        extra = f' stroke-dasharray="{dash}"' if dash else ''
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{extra}/>')

    def text(self, x, y, lines, size=22, color=INK, anchor='start', weight=400, line_height=None):
        if isinstance(lines, str): lines = lines.split('\n')
        spacing = line_height or size * 1.35
        self.parts.append(f'<text x="{x}" y="{y}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-weight="{weight}">')
        for i, line in enumerate(lines):
            self.parts.append(f'<tspan x="{x}" dy="{0 if i == 0 else spacing}">{escape(line)}</tspan>')
        self.parts.append('</text>')

    def arrow(self, points, label=None, lx=None, ly=None, color=INK, dashed=False):
        path = 'M' + ' L'.join(f'{x},{y}' for x, y in points)
        self.parts.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round" marker-end="url(#arrow{color[1:]})"' + (' stroke-dasharray="8 6"' if dashed else '') + '/>')
        if label:
            width = len(label) * 10 + 16
            self.rect(lx - width / 2, ly - 20, width, 28, 'white', 'none', 0, sw=0)
            self.text(lx, ly, label, 18, color, anchor='middle')

    def box(self, x, y, w, h, title, sub=None, tone='blue', size=23):
        fill, stroke = PALETTE[tone]
        self.rect(x, y, w, h, fill, stroke)
        titles = title.split('\n')
        self.text(x+w/2, y+36, titles, size, anchor='middle', weight=600, line_height=29)
        if sub:
            self.text(x+w/2, y+36+len(titles)*29+12, sub, 18, MUTED, anchor='middle', line_height=25)

    def diamond(self, cx, cy, rx, ry, title):
        fill, stroke = PALETTE['amber']
        self.parts.append(f'<path d="M{cx},{cy-ry} L{cx+rx},{cy} L{cx},{cy+ry} L{cx-rx},{cy} Z" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        self.text(cx, cy-4, title, 21, anchor='middle', weight=600, line_height=28)

    def aws(self, key, cx, cy, title, sub=None, icon_size=72):
        data = base64.b64encode((ICONS/f'{key}.svg').read_bytes()).decode()
        self.parts.append(f'<image x="{cx-icon_size/2}" y="{cy-icon_size/2}" width="{icon_size}" height="{icon_size}" href="data:image/svg+xml;base64,{data}"/>')
        labels = title.split('\n')
        self.text(cx, cy+67, labels, 23, anchor='middle', line_height=27)
        if sub: self.text(cx, cy+67+len(labels)*27+5, sub, 18, MUTED, anchor='middle', line_height=24)

    def footer(self, lines):
        self.parts.append(f'<path d="M64,{self.height-104} H{self.width-64}" stroke="#d9e0e6"/>')
        self.text(64, self.height-70, lines, 18, MUTED, line_height=27)

    def save(self):
        path = OUT / f'{self.slug}.svg'
        path.write_text('\n'.join(self.parts+['</svg>']), encoding='utf-8')
        return {'file': path.name, 'width': self.width, 'height': self.height}


def hosting():
    d = Diagram('01-aws-full-stack', 'AWS full-stack and cloud hosting',
        'Citereel: an evidence-backed video-production app. Deployed resource inventory checked 12 September 2026.', 2460, 1660, 1)
    d.rect(300, 170, 2096, 1355, stroke=INK, radius=0, sw=3)
    d.rect(300, 170, 84, 64, INK, INK, 0)
    d.text(342, 211, 'aws', 30, 'white', anchor='middle', weight=600)
    d.text(408, 213, 'AWS Cloud / customer account', 29, weight=600)
    d.text(2365, 212, 'Regional services: us-east-1', 21, MUTED, anchor='end')
    # Main request path; arrows indicate requests or job handoffs, not network peering.
    d.arrow([(180, 360), (424, 360)], 'HTTPS', 257, 343)
    d.arrow([(516, 360), (640, 360), (640, 300), (774, 300)], 'Static files', 671, 282)
    d.arrow([(470, 489), (470, 604)], '/v1/*', 520, 558)
    d.arrow([(516, 650), (774, 650)], 'HTTP API', 645, 630)
    d.arrow([(866, 650), (1124, 650)], 'Enqueue', 995, 630)
    d.arrow([(1216, 650), (1474, 650)], 'SQS event', 1345, 630)
    d.arrow([(1566, 650), (1824, 650)], 'RunTask', 1684, 630)
    d.arrow([(1916, 650), (2164, 650)], 'Save / restore', 2043, 630)
    d.arrow([(820, 604), (820, 497), (1170, 497), (1170, 437)], 'Read / write state', 990, 480)
    d.arrow([(1870, 805), (1870, 883), (1850, 883), (1850, 964)], 'IAM invocation', 1850, 865)
    d.arrow([(1804, 1010), (1556, 1010)], 'Strands model calls', 1680, 990, '#9a7ac5')
    d.arrow([(1916, 650), (2040, 650), (2040, 880), (2200, 880), (2200, 964)], 'Narration', 2150, 864)
    # Browser outside the AWS boundary.
    d.rect(72, 301, 110, 76, '#f6f8fa', INK, 3)
    d.parts.append('<path d="M62 389 H192 M106 389 V400 H148 V389" fill="none" stroke="#24313f" stroke-width="3"/>')
    d.text(128, 443, ['Creator browser', 'Next.js studio'], 22, anchor='middle')
    d.text(128, 512, ['Create, review,', 'revise and download'], 18, MUTED, anchor='middle')
    d.aws('cloudfront', 470, 360, 'Amazon CloudFront', 'Global HTTPS entry')
    d.aws('s3', 820, 300, 'Amazon S3', ['Static Next.js export', 'Origin Access Control'])
    d.aws('dynamodb', 1170, 300, 'Amazon DynamoDB', ['Jobs, sessions, approvals', 'Shared API / worker / agent state'])
    d.aws('ecr', 1590, 300, 'Amazon ECR', ['Versioned container images', 'API, worker and agent'])
    d.text(2080, 296, ['The API owns authentication.', 'Session cookies stay HTTP-only;', 'AWS access uses service IAM roles.'], 21, MUTED, anchor='middle', line_height=30)
    d.aws('api', 470, 650, 'Amazon API Gateway', 'HTTP API')
    d.aws('lambda', 820, 650, 'AWS Lambda', ['FastAPI application', 'Auth, jobs and decisions'])
    d.aws('sqs', 1170, 650, 'Amazon SQS', 'Production queue')
    d.aws('lambda', 1520, 650, 'AWS Lambda', ['Dispatcher', 'Conditional worker slots'])
    d.rect(1710, 535, 310, 270, 'none', '#718ec4', 0, '8 5')
    d.text(1725, 566, 'VPC / public subnets', 20, '#526e9c')
    d.aws('fargate', 1870, 650, 'AWS Fargate', ['ECS production worker', 'Playwright + FFmpeg'])
    d.aws('s3', 2210, 650, 'Amazon S3', ['Private recordings, MP4s', 'Posters and QA artifacts'])
    d.aws('bedrock', 1510, 1010, 'Amazon Bedrock', 'Configured foundation model')
    d.aws('agentcore', 1850, 1010, 'Amazon Bedrock\nAgentCore Runtime', 'One Strands planning agent')
    d.aws('polly', 2200, 1010, 'Amazon Polly', 'Speech synthesis')
    d.text(510, 978, 'PRIVATE EXPORT DELIVERY', 17, weight=600)
    d.text(510, 1018, ['Authenticated API issues a 5-minute', 'S3 presigned URL. The creator then', 'plays or downloads the private artifact.'], 22, MUTED, line_height=31)
    d.parts.append('<path d="M338 1214 H2358" stroke="#d9e0e6" stroke-width="2"/>')
    d.text(338, 1250, 'OPERATIONS AND RECOVERY', 18, MUTED, weight=600)
    d.arrow([(1026, 1350), (1090, 1350), (1090, 1284), (1690, 1284), (1690, 1304)], color='#8995a3', dashed=True)
    d.arrow([(1376, 1350), (1644, 1350)], color='#8995a3', dashed=True)
    d.arrow([(1736, 1350), (1920, 1350)], color='#8995a3', dashed=True)
    d.aws('cloudwatch', 560, 1350, 'Amazon CloudWatch', ['Service logs and', 'operations dashboard'], 60)
    d.aws('eventbridge', 980, 1350, 'Amazon EventBridge', 'ECS stopped-task events', 60)
    d.aws('sqs', 1330, 1350, 'Amazon SQS', 'Dead-letter queue', 60)
    d.aws('lambda', 1690, 1350, 'AWS Lambda', 'Recovery handler', 60)
    d.text(1950, 1348, ['Update DynamoDB:', 'block interrupted attempt,', 'release its worker slot.'], 21, MUTED, line_height=30)
    d.footer(['Worker tasks have no inbound security-group rules; public websites are read through bounded capture controls.',
        'Solid arrows: primary requests / handoffs. Dashed arrows: recovery events. AWS icons: official July 2026 package.'])
    return d.save()


def backend():
    d = Diagram('02-backend-production-workflow', 'Backend production workflow',
        'From an authorized website and creator brief to a reviewed, private video export.', 2280, 1370, 2)
    xs = [70, 440, 810, 1180, 1550, 1920]
    w = 290
    top = [
        ('Creator brief', 'Website, format, audience\nCapture authorization', 'green'),
        ('Authenticated API', 'Validate request + ownership\nPersist idempotent job', 'blue'),
        ('Queue + dispatcher', 'SQS message\nLambda launches ECS task', 'blue'),
        ('Fargate worker', 'Claim active attempt\nRenew job lease', 'blue'),
        ('Inspect sources', 'Bounded public-page fetch\nSave evidence', 'amber'),
        ('AgentCore + Strands', 'Reason over evidence\nSave plan + claim ledger', 'purple'),
    ]
    for i,(title,sub,tone) in enumerate(top):
        d.box(xs[i], 230, w, 165, title, sub, tone, 23)
        if i<5: d.arrow([(xs[i]+w,312),(xs[i+1],312)])
    d.arrow([(2065,395),(2065,462),(215,462),(215,540)],
        'Validated storyboard; pause for creator review',1140,449,color='#6b9c7c')
    lower = [
        ('Review storyboard', 'Creator checks copy,\nnarration and cited claims', 'green'),
        ('Approve + requeue', 'New attempt\nResume existing plan', 'green'),
        ('Capture or reuse', 'Playwright scene recordings\nS3 checkpoints + hashes', 'amber'),
        ('Narrate', 'Amazon Polly\nScene speech tracks', 'amber'),
        ('Compose + validate', 'FFmpeg / ffprobe\nCaptions, media QA, SHA-256', 'blue'),
        ('Save private export', 'Versioned S3 artifacts\nState: ready_for_review', 'green'),
    ]
    for i,(title,sub,tone) in enumerate(lower):
        d.box(xs[i],540,w,170,title,sub,tone,23)
        if i<5:d.arrow([(xs[i]+w,625),(xs[i+1],625)])
    d.text(215,765,'Worker exits while awaiting approval.',17,MUTED,anchor='middle')
    d.text(953,765,'Unchanged recordings are reused.',17,MUTED,anchor='middle')
    d.arrow([(2065,710),(2065,888)],'Private access',2065,842,color='#6b9c7c')
    d.box(1875,890,355,195,'Creator review / download','Playback, export approval\nand presigned downloads\nNo automatic publication','green')
    d.rect(70,850,1730,345,'#fbfcfd','#d9e0e6',6)
    d.text(100,893,'Failure and retry path',24,weight=600)
    recovery = [
        ('Task stop / DLQ','EventBridge or\nexhausted queue delivery','red'),
        ('Recovery Lambda','Fence by attempt\nMark job blocked','blue'),
        ('Creator retries','Explicit retry\nNew queued attempt','green'),
        ('Resume safely','Restore hashed checkpoints\nPreserve prior exports','amber'),
    ]
    rxs=[100,525,950,1375]
    for i,(title,sub,tone) in enumerate(recovery):
        d.box(rxs[i],925,350,170,title,sub,tone,22)
        if i<3:d.arrow([(rxs[i]+350,1010),(rxs[i+1],1010)],color='#8995a3',dashed=True)
    d.text(100,1152,'DynamoDB stores job state, attempts, approvals and receipts throughout the workflow.',21,MUTED)
    d.footer(['Default review-enabled path shown. Automatic capture may skip the plan pause only when creator-authorized and no claims need review.',
        'Source: worker/runner.py, agent/remote.py, API/main.py, infra/dispatcher.py and infra/recovery.py.'])
    return d.save()


def agent_loop():
    d=Diagram('03-strands-agent-loop','Strands agent reasoning and tool loop',
        'One evidence-grounded planning agent, hosted in Amazon Bedrock AgentCore Runtime.',2200,1160,3)
    d.rect(390,195,1430,495,'none','#ad7fc4',8,'8 7')
    d.text(420,238,'Strands agent loop / launchpad_concierge',26,'#568b77',weight=600)
    d.box(60,335,270,155,'Input + context','Creator brief, evidence\nOptional revision context','green')
    d.box(460,335,300,155,'Reasoning (LLM)','Amazon Bedrock\nConfigured model','purple')
    d.box(880,335,300,155,'Tool selection','Choose a scoped tool\nProductionPolicy gate','blue')
    d.box(1300,335,420,155,'Tool execution','Return evidence, validation\nresult or a saved plan','amber')
    d.box(1890,335,260,185,'Worker receives result','Validated storyboard\nor human-decision pause','green',22)
    d.arrow([(330,413),(460,413)],color='#6b9c7c')
    d.arrow([(760,413),(880,413)],color='#9a7ac5')
    d.arrow([(1180,413),(1300,413)],color='#718ec4')
    d.arrow([(1720,413),(1890,413)],'Done',1804,395,color='#6b9c7c')
    d.arrow([(1510,490),(1510,604),(610,604),(610,490)],
        'Tool results and validation errors feed back',1070,590,color='#c89b58')
    d.text(420,659,'Stop for a human decision or when execution limits are reached.',19,MUTED)
    d.text(60,772,'Four scoped tools',26,weight=600)
    tools=[
        ('get_production_brief','Read format, audience, duration\nand the creator\'s call to action.','blue'),
        ('inspect_authorized_site','Read inspected site evidence;\npage content is untrusted data.','amber'),
        ('submit_storyboard','Validate schema, sources and copy;\nsave the plan and claim ledger.','purple'),
        ('request_human_decision','Record missing support or ambiguity;\nset a pending human decision.','green'),
    ]
    for i,(title,sub,tone) in enumerate(tools):d.box(60+i*535,810,505,155,title,sub,tone,21)
    d.footer(['Planning limits: 8 turns, 45,000 total tokens, 10,000 output tokens and a maximum of 10 tool calls.',
        'Source: services/agent/src/launchpad_agent/concierge.py, policies.py and runtime.py.'])
    return d.save()


def hooks():
    d=Diagram('04-agent-policy-hooks','Agent lifecycle and policy hooks',
        'The actual ProductionPolicy callbacks: BeforeModelCallEvent, BeforeToolCallEvent and AfterToolCallEvent.',2600,1260,4)
    y=320
    d.box(60,y,200,160,'Invocation','Active job,\nattempt + session','green',22)
    d.box(330,y,280,160,'BeforeModelCallEvent','Check cancellation,\nhuman decision + budget','blue',21)
    d.box(690,y,220,160,'Bedrock model','Reason and\nrequest a tool','purple',22)
    d.box(990,y,280,160,'BeforeToolCallEvent','Count call; check\nstate + prerequisites','amber',21)
    d.diamond(1410,400,80,77,'Tool\nallowed?')
    d.box(1560,y,220,160,'Execute tool','Run the selected\nscoped function','green',22)
    d.box(1870,y,280,160,'AfterToolCallEvent','Verify actual result\nand tool postcondition','blue',21)
    d.box(2340,y,200,160,'Tool result','Return feedback\nto the agent','green',22)
    for a,b in [(260,330),(610,690),(910,990),(1270,1330),(1490,1560),(1780,1870),(2150,2340)]:
        d.arrow([(a,400),(b,400)])
    d.text(1522,378,'Yes',18,'#6b9c7c',anchor='middle')
    d.box(340,580,260,140,'Stop model call','Human decision,\ncancellation or budget','red',22)
    d.arrow([(470,480),(470,580)],'Blocked',526,537,color='#c7837b',dashed=True)
    d.box(1280,580,260,140,'Cancel tool','Set cancel_tool\nwith the rejection reason','red',22)
    d.arrow([(1410,477),(1410,580)],'No',1443,537,color='#c7837b',dashed=True)
    d.arrow([(1540,650),(2010,650),(2010,480)],'Cancellation recorded',1784,632,color='#c7837b',dashed=True)
    d.arrow([(2440,480),(2440,790),(288,790),(288,267),(470,267),(470,320)],
        'Next model iteration receives tool results or cancellation feedback',1430,774,color='#9a7ac5')
    details=[
        ('Before tool execution',
         'Allow at most 10 calls. Block calls after a plan is saved\nor a human decision is pending. Read the brief and inspect\nthe site before submit_storyboard may run.','amber'),
        ('After tool execution',
         'Check exceptions, cancellation and result status. A rejected\nstoryboard is not a successful submission until a plan exists.\nOnly successful postconditions satisfy prerequisites.','blue'),
        ('Attempt fencing and audit',
         'AttemptStore checks owner, active attempt, planning state,\ncancellation and session ID before state access. Policy\nreceipts record passed or blocked outcomes in job state.','green'),
    ]
    for i,(title,sub,tone) in enumerate(details):d.box(60+i*855,865,810,210,title,sub,tone,24)
    d.footer(['These are policy decisions, not an in-tool user approval dialog. Creator plan/export approvals happen through the API and studio.',
        'Source: services/agent/src/launchpad_agent/policies.py and runtime.py.'])
    return d.save()


manifest = [hosting(), backend(), agent_loop(), hooks()]
(OUT/'source'/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(manifest))
