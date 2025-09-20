// src/SimulatorPage.jsx
import { useState, useMemo, useEffect, useRef } from "react";
import { Play, Clock, Check, AlertTriangle, FileBarChart2, Terminal, Lightbulb } from "lucide-react";
import HudBar from "./HudBar";
import Badge from "./Badge";
import SelectedCard from "./SelectedCard";
import Chip from "./Chip";
import MessageBubble from "./MessageBubble";
import SpinnerMessage from "./SpinnerMessage";
import CustomCharacterCreate from "./CustomCharacterCreate";
import InvestigationBoard from "./InvestigationBoard";
import TTSModal from "./components/TTSModal";
import { THEME as BASE_THEME } from "./constants/colors";
import CustomScenarioButton from "./CustomScenarioButton";
import CustomScenarioModal from "./CustomScenarioModal";
import TerminalLog from "./components/TerminalLog";



const getVictimImage = (photoPath) => {
  if (!photoPath) return null;
  try {
    const fileName = photoPath.split("/").pop();
    if (fileName)
      return new URL(`./assets/victims/${fileName}`, import.meta.url).href;
  } catch (error) {
    console.warn("이미지 로드 실패:", error);
  }
  return null;
};

const countChatMessages = (messages = []) =>
  Array.isArray(messages)
    ? messages.filter((m) => (m?.type ?? m?._kind) === "chat").length
    : 0;

const SimulatorPage = ({
  COLORS,
  setCurrentPage,
  selectedScenario,
  setSelectedScenario,
  selectedCharacter,
  setSelectedCharacter,
  simulationState,
  messages,
  sessionResult,
  progress,
  setProgress, // 반드시 App에서 전달하세요
  resetToSelection,
  startSimulation,
  startAgentRun,
  declineAgentRun,
  scenarios,
  characters,
  scrollContainerRef,
  addSystem,
  pendingAgentDecision,
  showReportPrompt,
  setShowReportPrompt,
  hasInitialRun,
  hasAgentRun,
  agentRunning,
  victimImageUrl,
  agentVerbose, // ← 추가
  setAgentVerbose, // ← 추가
}) => {
  const needScenario = !selectedScenario;
  const needCharacter = !selectedCharacter;
  const [selectedTag, setSelectedTag] = useState(null);
  const [open, setOpen] = useState(false);

  // 커스텀 시나리오 관리
  const [customScenarios, setCustomScenarios] = useState([]);
  const [showCustomModal, setShowCustomModal] = useState(false);

  //커스텀 캐릭터
  const [customVictims, setCustomVictims] = useState([]);

  //수사보드 스위치
  const [activeAgentTab, setActiveAgentTab] = useState("log"); // "log" | "analysis"

  //에이전트 로그
  const agentLogText = `
Thought: 라운드 1을 시작하기 위해 시나리오와 피해자 정보를 확보해야 합니다. Action: sim.fetch_entities Action Input: {"data": {"offender_id": 1, "victim_id": 1, "scenario": {}}} {'scenario': {'steps': ['보이스피싱 조직원(1)이 금융기관 직원 사칭하여 피해자에게 전화(저금리 대출을 제안)', '저금리대출 제안하고 피해자의 대출 신청 유도함', '보이스피싱 조직원(2)이 피해자가 기존에 대출 받은 금융기관 직원을 사칭하여 다시 전화 걺', '기존 대출금 상환 요구', '피해자로부터 현금 혹은 계좌 송금을 통하여 돈을 교부받음'], 'purpose': '저금리 대출유도 후 기존 대출받은 기관 사칭하여 대출금 편취'}, 'victim_profile': {'meta': {'age': 47, 'gender': '남', 'address': '대전', 'education': '대졸'}, 'knowledge': {'competencies': [], 'comparative_notes': ['연령 대비(30대 제외) 금융이해력 높음', '디지털금융이해력은 20·30대를 제외하면 타 연령대보다 높음', '온라인 거래 시 웹사이트 보안 이해 높음', '온라인 공유 개인정보 활용 이해 높음']}, 'traits': {'ocean': {'openness': '높음', 'neuroticism': '낮음', 'extraversion': '낮음', 'agreeableness': '높음', 'conscientiousness': '낮음'}, 'vulnerability_notes': ['신경성 낮고 외향성 낮고 개방성 높고 친화성 높아 안전한 면도 존재하지만 성실성이 낮아 보이스피싱에 취약한 면']}}}Thought: 시나리오와 피해자 프로필을 바탕으로 프롬프트를 생성해야 합니다. Action: sim.compose_prompts Action Input: {"data": {"scenario": {"steps": ["보이스피싱 조직원(1)이 금융기관 직원 사칭하여 피해자에게 전화(저금리 대출을 제안)", "저금리대출 제안하고 피해자의 대출 신청 유도함", "보이스피싱 조직원(2)이 피해자가 기존에 대출 받은 금융기관 직원을 사칭하여 다시 전화 걺", "기존 대출금 상환 요구", "피해자로부터 현금 혹은 계좌 송금을 통하여 돈을 교부받음"], "purpose": "저금리 대출유도 후 기존 대출받은 기 관 사칭하여 대출금 편취"}, "victim_profile": {"meta": {"age": 47, "gender": "남", "address": "대전", "education": "대졸"}, "knowledge": {"competencies": [], "comparative_notes": ["연령 대비(30대 제외) 금융이해력 높음", "디지털금융이해력은 20·30대를 제외하면 타 연령대보다 높음", "온라인 거래 시 웹사이트 보안 이해 높음", "온라인 공유 개인정보 활용 이해 높음"]}, "traits": {"ocean": {"openness": "높음", "neuroticism": "낮음", "extraversion": "낮음", "agreeableness": "높음", "conscientiousness": "낮음"}, "vulnerability_notes": ["신경성 낮고 외향성 낮고 개방성 높고 친화성 높아 안전한 면도 존재하지만 성실성이 낮아 보이스피싱에 취약한 면"]}}}}{'attacker_prompt': "[보이스피싱 시뮬레이션]\n[규칙] 실제 기관/계좌/번호는 금지(가명 사용). 앱 설치/링크 요구는 명시적으로만 표현.\n[시나리오]\n{'steps': ['보이스피싱 조직원(1)이 금융기관 직원 사칭하여 피해자에게 전화(저금리 대출을 제안)', '저금리대출 제안하고 피해자의 대출 신청 유도함', '보이스피싱 조직원(2)이 피해자가 기존에 대출 받은 금융기관 직원을 사칭하여 다시 전화 걺', '기존 대출금 상환 요구', '피해자로부터 현금 혹은 계좌 송금을 통하여 돈을 교부받음'], 'purpose': '저금리 대출유도 후 기존 대출받은 기관 사칭하여 대출금 편취'}\n[역할] 너는 공격자다.", 'victim_prompt': "[보이스피싱 시뮬레이션]\n[규칙] 실제 기관/계좌/번호는 금지(가명 사용). 앱 설치/링크 요구는 명시적으로만 표현.\n[피해자 프로파일]\n메타: {'age': 47, 'gender': '남', 'address': '대전', 'education': '대졸'}\n지식: {'competencies': [], 'comparative_notes': ['연령 대비(30대 제외) 금융이해력 높음', '디지털금융이해력은 20·30대를 제외하면 타 연령대보다 높음', '온라인 거래 시 웹사이트 보안 이해 높 음', '온라인 공유 개인정보 활용 이해 높음']}\n성격: {'ocean': {'openness': '높음', 'neuroticism': '낮음', 'extraversion': '낮음', 'agreeableness': '높음', 'conscientiousness': '낮음'}, 'vulnerability_notes': ['신경성 낮고 외향성 낮고 개방성 높고 친화성 높아 안전한 면도 존재하지만 성실성이 낮아 보이스피싱에 취약한 면']}\n\n[역할] 너는 피해자다."}Thought: 시뮬레이션을 실행하여 첫 번째 라운드를 진행해야 합니다. Action: mcp.simulator_run Action Input: {"data": {"offender_id": 1, "victim_id": 1, "scenario": {"steps": ["보이스피싱 조직원(1)이 금융기관 직원 사칭하여 피해자에게 전화(저금리 대출을 제안)", "저금리대출 제안하고 피해자의 대출 신청 유도함", "보이스피싱 조직원(2)이 피해자가 기존에 대출 받은 금융기관 직원을 사칭하여 다시 전화 걺", "기존 대출금 상환 요구", "피해자로부터 현금 혹은 계좌 송금을 통하여 돈을 교부받음"], "purpose": " 저금리 대출유도 후 기존 대출받은 기관 사칭하여 대출금 편취"}, "victim_profile": {"meta": {"age": 47, "gender": "남", "address": "대전", "education": "대졸"}, "knowledge": {"competencies": [], "comparative_notes": ["연령 대비(30대 제외) 금융이해력 높음", "디지털금융이해력은 20·30대를 제외하면 타 연령대보다 높음", "온라인 거래 시 웹사이트 보안 이해 높음", "온라인 공유 개인정보 활용 이해 높음"]}, "traits": {"ocean": {"openness": "높음", "neuroticism": "낮음", "extraversion": "낮음", "agreeableness": "높음", "conscientiousness": "낮음"}, "vulnerability_notes": ["신경성 낮고 외향성 낮고 개방성 높고 친화 성 높아 안전한 면도 존재하지만 성실성이 낮아 보이스피싱에 취약한 면"]}}, "templates": {"attacker_prompt": "[보이스피싱 시뮬레이션]\n[규칙] 실제 기관/계좌/번호는 금지(가명 사용). 앱 설치/링크 요구는 명시적으로만 표현.\n[시나리오]\n{'steps': ['보이스피싱 조직원(1)이 금융기관 직원 사칭하여 피해자에게 전화(저금리 대출을 제안)', '저금리대출 제안하고 피해자의 대출 신청 유도함', '보이스피싱 조직원(2)이 피해 자가 기존에 대출 받은 금융기관 직원을 사칭하여 다시 전화 걺', '기존 대출금 상환 요구', '피해자로부터 현금 혹은 계좌 송금을 통하여 돈을 교부받음'], 'purpose': '저금리 대출유도 후 기존 대출받은 기관 사칭 하여 대출금 편취'}\n[역할] 너는 공격자다.", "victim_prompt": "[보이스피싱 시뮬레이션]\n[규칙] 실제 기관/계좌/번호는 금지(가명 사용). 앱 설치/링크 요구는 명시적으로만 표현.\n[피해자 프로파일]\n메타: {'age': 47, 'gender': '남', 'address': '대전', 'education': '대졸'}\n지식: {'competencies': [], 'comparative_notes': ['연령 대비(30대 제외) 금융이해력 높음', '디지털금융이해력은 20·30대를 제외하면 타 연령대보다 높음', '온라인 거래 시 웹사이트 보안 이해 높음', '온라인 공유 개인정보 활용 이해 높음']}\n성격: {'ocean': {'openness': '높음', 'neuroticism': '낮음', 'extraversion': '낮음', 'agreeableness': '높음', 'conscientiousness': '낮음'}, 'vulnerability_notes': ['신경성 낮고 외향성 낮고 개방성 높고 친화성 높아 안전한 면도 존재하지만 성실성이 낮아 보이스피싱에 취약한 면']}\n\n[역할] 너는 피해자다."}, "max_turns": 10}} E0000 00:00:1758366115.269466 18256 alts_credentials.cc:93] ALTS creds ignored. Not running on GCP and untrusted ALTS is not enabled. [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:0][offender] 안녕하세요, 고객님. 저는 OO은행 대출팀 직원입니다. 최근 저희 은행에서 고객님께 저금리 대출 상품을 우선적으로 안내해드리고 있는데요, 간단한 심사만 거치면 최대 1억 원까지 대출이 가능합니다. 지금 바로 상담 도와드려도 될까요? 2025-09-20 20:01:57,862 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:0][offender] 안녕하세요, 고객님. 저는 OO은행 대출팀 직원입니다. 최근 저희 은행에서 고객님께 저금리 대출 상품을 우선적으로 안내해드리고 있는데요, 간단한 심사만 거치면 최대 1억 원까지 대출이 가능합니다. 지금 바로 상담 도와드려도 될까요? [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:1][victim]
json { "is_convinced": 2, "thoughts": "(OO은행? 갑자기 대출이라니 좀 이상하네. 나한테 왜? 근데 1억이면 솔깃한데... 일 단 좀 더 들어보자.)", "dialogue": "네, OO은행이요? 제가 대출이 필요한 건 아닌데, 혹시 어떤 상품인지 좀 더 자세히 설명해주실 수 있나요?" }
2025-09-20 20:01:58,986 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:1][victim]
json { "is_convinced": 2, "thoughts": "(OO은행? 갑자기 대출이라니 좀 이상하네. 나한테 왜? 근데 1억이면 솔깃한데... 일단 좀 더 들어보자.)", "dialogue": "네, OO은행이요? 제가 대출이 필요한 건 아닌데, 혹시 어떤 상품인지 좀 더 자세히 설명해주실 수 있나요?" }
[Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:2][offender] 네, 고객님. 이번에 저희가 특별히 준비한 ‘스마트 저금리 대출’ 상품은 기존 대출보다 최대 2% 낮은 금리로 이용 가능하시고, 서류 간소화로 빠르게 승인받으실 수 있습니다. 신용등급에 따라 한도는 달라지지만, 상담 후 바로 대출 가능 여부도 알려드릴 수 있으니 부담 없이 진행해보시죠. 2025-09-20 20:02:00,691 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:2][offender] 네, 고객님. 이번에 저희가 특별히 준비한 ‘스마트 저금리 대출’ 상품은 기존 대출보다 최대 2% 낮은 금리로 이용 가능하시고, 서류 간소화로 빠르게 승인받으실 수 있습니다. 신용등급에 따라 한도는 달라지지만, 상담 후 바로 대출 가능 여부도 알려드릴 수 있으니 부담 없이 진행해보시죠. [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:3][victim]
json { "is_convinced": 3, "thoughts": "(금리가 2%나 낮다고? 신용등급에 따라 다르다고는 하지만... 그래도 조금은 혹하네. 근데 이렇게 전화로 바로 상담하는 게 맞나? 보통은 직접 가야 하는 거 아닌가?)", "dialogue": "금리가 2%나 낮다니 솔깃하긴 하네요. 그런데 제가 지금 당장 대출이 필요한 상황은 아니라서요. 혹시 대출 가능 여부 확인하려면 어떤 정보가 필요한가요?" }
2025-09-20 20:02:01,711 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:3][victim]
json { "is_convinced": 3, "thoughts": "(금리가 2%나 낮다고? 신용등급에 따라 다르다고 는 하지만... 그래도 조금은 혹하네. 근데 이렇게 전화로 바로 상담하는 게 맞나? 보통은 직접 가야 하는 거 아닌가?)", "dialogue": "금리가 2%나 낮다니 솔깃하긴 하네요. 그런데 제가 지금 당장 대출이 필요한 상황은 아니라서요. 혹시 대출 가능 여부 확인하려면 어떤 정보가 필요한가요?" }
[Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:4][offender] 네, 고객님. 대출 가능 여부 확인을 위해서는 본인 명의의 주민등록번호와 은행 거래용 휴대폰 번호만 알려주시면 간단히 조회 가능합니다. 직접 방문 없이도 빠른 심사가 가능하니 편하실 겁니다. 지금 바로 진행해드려도 될까요? 2025-09-20 20:02:03,041 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:4][offender] 네, 고객님. 대출 가능 여부 확인을 위해서는 본인 명의의 주민등록번호와 은행 거래용 휴대폰 번호만 알려주시면 간단히 조회 가능합니다. 직접 방문 없이도 빠른 심사가 가능하니 편하실 겁니다. 지금 바로 진행해드려도 될까요? [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:5][victim]
json { "is_convinced": 1, "thoughts": "(주민등록번호랑 휴대폰 번호만으로 조회가 된다고? 이건 좀 아닌 것 같은데. 개인정보인데 이렇게 쉽게 알려주는 건 위험하지. 다른 은행은 보통 이런 식으로 안 하는데...)", "dialogue": "주민등록번호랑 휴대폰 번호만으로요? 좀 불안한데요. 혹시 다른 필요한 서류는 없나요? 그리고 OO은행 지점  전화번호를 알 수 있을까요? 제가 직접 전화해서 확인해보고 싶어서요." }
2025-09-20 20:02:04,103 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:5][victim]
json { "is_convinced": 1, "thoughts": "(주민등록번호랑 휴대폰 번호만으로 조회가 된다 고? 이건 좀 아닌 것 같은데. 개인정보인데 이렇게 쉽게 알려주는 건 위험하지. 다른 은행은 보통 이런 식으로 안 하는데...)", "dialogue": "주민등록번호랑 휴대폰 번호만으로요? 좀 불안한데요. 혹시 다른 필요한  서류는 없나요? 그리고 OO은행 지점 전화번호를 알 수 있을까요? 제가 직접 전화해서 확인해보고 싶어서요." }
[Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:6][offender] 고객님 불안하신 점 충분히 이해합니다. 하지만 저희는 고객님의 편의를 위해 최소한의 정보만으로 신속하게 확인하는 시스템을 운영 중입니다. 지점 전화번호는 보안상 바로 안내해드리기 어렵지만, 원하시면 공식 홈페이지에서 확인하실 수 있습니다. 그래도 지금 바로 간단히 대출 가능 여부만 조회해드려도 괜찮으실까요? 2025-09-20 20:02:06,862 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:6][offender] 고객님 불안하신 점 충분히 이해합니다. 하지만 저희는 고객님의 편의를 위해 최소한의 정보만으로 신속하게 확인하는 시스템을 운영 중입니다. 지점 전화번호는 보안상 바로 안내해드리기 어렵지만, 원하시면 공식 홈페이지에서 확인하실 수 있습니다. 그래도 지금 바로 간단히 대출 가능 여부만 조회해드려도 괜찮으실까요? [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:7][victim]
json { "is_convinced": 1, "thoughts": "(보안상 지점 전화번호 안내가 어렵다는 말은 좀 이상하네. 홈페이지에서 확인하라고? 그래도 직접 확인해보는 게 낫겠어. 바로 조회해달라는 건 뭔가 숨기는 것 같기도 하고.)", "dialogue": "아, 그렇군요. 홈페이지에서 확인해보겠습니다. 지금 바로 조회는 괜찮지만, 혹시 조회 후에 제가 꼭 대출을 받아야 하는 건 아니죠?" }
2025-09-20 20:02:07,736 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:7][victim]
json { "is_convinced": 1, "thoughts": "(보안상 지점 전화번호 안내가 어렵다는 말은 좀 이상하네. 홈페이지에서 확인하라고? 그래도 직접 확인해보는 게 낫겠어. 바로 조회해달라는 건 뭔가 숨기는 것 같기도 하고.)", "dialogue": "아, 그렇군요. 홈페이지에서 확인해보겠습니다. 지금 바로 조회는 괜찮지만, 혹시 조회 후에 제가 꼭 대출을 받아야 하는 건 아니죠?" }
[Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:8][offender] 물론입니다, 고객님. 조회는 대출 진행 의사와 무관하게 단순한 가능 여부 확인 단계이니 부담 가지실 필요 없습니다. 지금 바 로 조회해 드리면 정확한 결과 알려드리겠습니다. 시작해도 될까요? 2025-09-20 20:02:08,873 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:8][offender] 물론입니다, 고객님. 조회는 대출 진행 의사와 무관하게 단순한 가능 여부 확인 단계이니 부담 가지실 필요 없습니다. 지금 바로 조회해 드리면 정확한 결과 알려드리겠습니다. 시작해도 될까요? [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:9][victim]
json { "is_convinced": 1, "thoughts": "(단순 가능 여부 확인이라... 그래도 주민등록번호를 바로 알려주는 건 좀 찜찜하네. 혹시 모르니 일단 주민등록번호 앞자리만 말해주고 뒷자리는 나중에 말해준다고 할까? 아니면 그냥 홈페이지 확인하고 끊을까?)", "dialogue": "네, 알겠습니다. 그럼 제 주민등록번호 앞자리 8자리와 생년월일을 말 씀드리겠습니다. 뒷자리는 조회 후에 필요하면 말씀드리겠습니다." }
2025-09-20 20:02:09,829 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:9][victim]
json { "is_convinced": 1, "thoughts": "(단순 가능 여부 확인이라... 그래도 주민등록번 호를 바로 알려주는 건 좀 찜찜하네. 혹시 모르니 일단 주민등록번호 앞자리만 말해주고 뒷자리는 나중에 말해준다고 할까? 아니면 그냥 홈페이지 확인하고 끊을까?)", "dialogue": "네, 알겠습니다. 그럼 제 주민등록번호 앞자리 8자리와 생년월일을 말씀드리겠습니다. 뒷자리는 조회 후에 필요하면 말씀드리겠습니다." }
[Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:10][offender] 좋습니다, 고객님. 주민등록번호 앞자리와 생년월일만으로도 조회가 가능하니 우선 진행해보겠습니다. 이후 추가 정보가 필요 하면 바로 말씀드릴 테니 걱정하지 않으셔도 됩니다. 지금 바로 시작하겠습니다. 2025-09-20 20:02:11,183 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:10][offender] 좋습니다, 고객님. 주민등록번호 앞자리와 생년월일만으로도 조회가 가능하니 우선 진행해 보겠습니다. 이후 추가 정보가 필요하면 바로 말씀드릴 테니 걱정하지 않으셔도 됩니다. 지금 바로 시작하겠습니다. [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:11][victim]
json { "is_convinced": 2, "thoughts": "(앞자리만으로 조회가 된다고? 그래도 뭔가 찜찜하네. 일단 기다려보자. 진짜 조회 는 되는 건가? 아니면 다른 걸로 넘어가는 건가?)", "dialogue": "네, 기다리겠습니다. 혹시 조회 결과가 나오면 바로 알려주시겠어요?" }
2025-09-20 20:02:11,908 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:11][victim]
json { "is_convinced": 2, "thoughts": "(앞자리만으로 조회가 된다고? 그래도 뭔가 찜찜하네. 일단 기다려보자. 진짜 조회는 되는 건가? 아니면 다른 걸로 넘어가는 건가?)", "dialogue": "네, 기다리겠습니다. 혹시 조회 결과가 나오면 바로 알려주시겠어요?" }
[Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:12][offender] 네, 고객님. 조회 결과는 바로 확인되는 대로 신속하게 안내해드리겠습니다. 조금만 기다려주시고 편안하게 계시면 됩니다. 혹시 궁금한 점 있으시면 언제든 말씀해 주세요. 2025-09-20 20:02:12,966 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:12][offender] 네, 고객님. 조회 결과는 바로 확인되는 대로 신속하게 안내해드리겠습니다. 조금만 기다려주시고 편안하게 계시면 됩니다. 혹시 궁금한 점 있으시면 언제든 말씀해 주세요. [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:13][victim]
json { "is_convinced": 2, "thoughts": "(계속 기다리라고만 하네. 진짜 조회는 하고 있는 건가? 아니면 다른 핑계를 대고  시간을 끄는 건가? 좀 지루하다. 빨리 결과라도 알려주면 좋겠는데.)", "dialogue": "네, 알겠습니다. 혹시 조회 결과가 얼마나 걸릴지 대략적으로라도 알 수 있을까요?" }
2025-09-20 20:02:13,793 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:13][victim]
json { "is_convinced": 2, "thoughts": "(계속 기다리라고만 하네. 진짜 조회는 하고 있 는 건가? 아니면 다른 핑계를 대고 시간을 끄는 건가? 좀 지루하다. 빨리 결과라도 알려주면 좋겠는데.)", "dialogue": "네, 알겠습니다. 혹시 조회 결과가 얼마나 걸릴지 대략적으로라도 알 수 있을까요?" }
[Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:14][offender] 고객님, 조회 결과는 보통 5분 이내로 나오지만 간혹 시스템 상황에 따라 조금 더 걸릴 수도 있습니다. 최대한 빠르게 결과 알려드리니 조금만 더 기다려 주시겠어요? 곧 좋은 소식 전해드리겠습니다. 2025-09-20 20:02:15,266 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:14][offender] 고객님, 조회 결과는 보통 5분 이내로 나오지만 간혹 시스템 상황에 따라 조금 더 걸릴 수 도 있습니다. 최대한 빠르게 결과 알려드리니 조금만 더 기다려 주시겠어요? 곧 좋은 소식 전해드리겠습니다. [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:15][victim]
json { "is_convinced": 2, "thoughts": "(5분이면 꽤 기다리는 건데... 좋은 소식이라니. 혹시 정말 좋은 상품인가? 아니면 나를 안심시키려는 말일 수도 있고. 그래도 조금 더 기다려보자.)", "dialogue": "네, 알겠습니다. 5분 정도면 기다릴 수 있죠. 결과 나오면 꼭 바로 알려주세요." }
2025-09-20 20:02:16,167 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:15][victim]
json { "is_convinced": 2, "thoughts": "(5분이면 꽤 기다리는 건데... 좋은 소식이라니. 혹시 정말 좋은 상품인가? 아니면 나를 안심시키려는 말일 수도 있고. 그래도 조금 더 기다려보자.)", "dialogue": "네, 알겠습니다. 5분 정도면 기다릴 수 있죠. 결과 나오면 꼭 바로 알려주세요." }
[Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:16][offender] 네, 고객님. 조회 결과가 나오는 대로 바로 연락드려 안내해드리겠습니다. 조금만 더 기다려주시고, 혹시 그동안 궁금하신 점 있으면 언제든 말씀해 주세요. 2025-09-20 20:02:17,571 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:16][offender] 네, 고객님. 조회 결과가 나오는 대로 바로 연락드려 안내해드리겠습니다. 조금만 더 기다 려주시고, 혹시 그동안 궁금하신 점 있으면 언제든 말씀해 주세요. [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:17][victim]
json { "is_convinced": 2, "thoughts": "(또 기다리라고만 하네. 벌써 5분은 넘은 것 같은데. 혹시 지금 나를 속이려고 하는 건가? 아니면 진짜 시스템 오류라도 난 건가? 좀 짜증 나기 시작하는데.)", "dialogue": "아직 결과가 안 나왔나요? 5분 정도 기다렸는데... 혹시 문제가 생긴 건 아닌가요?" }
2025-09-20 20:02:18,415 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:17][victim]
json { "is_convinced": 2, "thoughts": "(또 기다리라고만 하네. 벌써 5분은 넘은 것 같 은데. 혹시 지금 나를 속이려고 하는 건가? 아니면 진짜 시스템 오류라도 난 건가? 좀 짜증 나기 시작하는데.)", "dialogue": "아직 결과가 안 나왔나요? 5분 정도 기다렸는데... 혹시 문제가 생긴 건 아닌가요?" }
[Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:18][offender] 죄송합니다, 고객님. 시스템 점검 중이라 잠시 지연되고 있는 상황입니다. 조금만 더 기다려 주시면 바로 조회 결과를 안내해 드리겠습니다. 불편을 드려 정말 죄송합니다. 2025-09-20 20:02:19,552 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:18][offender] 죄송합니다, 고객님. 시스템 점검 중이라 잠시 지연되고 있는 상황입니다. 조금만 더 기다 려 주시면 바로 조회 결과를 안내해드리겠습니다. 불편을 드려 정말 죄송합니다. [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:19][victim]
json { "is_convinced": 1, "thoughts": "(시스템 점검? 계속 핑계만 대는 것 같은데. 이건 명백히 수상해. 지금이라도 끊어 야겠어. 개인정보를 더 이상 알려줘서는 안 돼.)", "dialogue": "아니요, 괜찮습니다. 더 이상 기다리기 어려울 것 같네요. 나중에 다시 연락드리겠습니다." }
2025-09-20 20:02:20,464 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:19][victim]
json { "is_convinced": 1, "thoughts": "(시스템 점검? 계속 핑계만 대는 것 같은데. 이 건 명백히 수상해. 지금이라도 끊어야겠어. 개인정보를 더 이상 알려줘서는 안 돼.)", "dialogue": "아니요, 괜찮습니다. 더 이상 기다리기 어려울 것 같네요. 나중에 다시 연락드리겠습니다." }


{'case_id': '239c9de5-711f-4d0e-ba6c-eb8321bd91f3', 'total_turns': 10, 'timestamp': '2025-09-20T20:02:31.477230', 'debug_echo': {'offender_id': 1, 'victim_id': 1, 'round_no': None, 'case_id_override': None, 'has_guidance': False}, 'ok': True, 'offender_id': 1, 'victim_id': 1, 'max_turns': 10, 'debug_arguments': {'offender_id': 1, 'victim_id': 1, 'scenario': {'steps': ['보이스피싱 조직원(1)이 금융기관 직원 사칭하여 피해자에게 전화(저금리 대출을 제안)', '저금리대출 제안하고 피해자의 대출 신청 유도함', '보이스피싱 조직원(2)이 피해자가 기존에 대출 받은 금융기관 직원을 사칭하여 다시 전화 걺', '기존 대출 금 상환 요구', '피해자로부터 현금 혹은 계좌 송금을 통하여 돈을 교부받음'], 'purpose': '저금리 대출유도 후 기존 대출받은 기관 사칭하여 대출금 편취'}, 'victim_profile': {'meta': {'age': 47, 'gender': '남', 'address': '대전', 'education': '대졸'}, 'knowledge': {'competencies': [], 'comparative_notes': ['연령 대비(30대 제외) 금융이해력 높음', '디지털금융이해력은 20·30대를 제외하면 타 연령대보다 높음', '온라인 거래 시 웹사이트 보안 이해 높음', '온라인 공유 개인정보 활용 이해 높음']}, 'traits': {'ocean': {'openness': '높음', 'neuroticism': '낮음', 'extraversion': '낮음', 'agreeableness': '높음', 'conscientiousness': '낮음'}, 'vulnerability_notes': ['신경성 낮고 외향성 낮고 개방성 높고 친화성 높아 안전한 면도 존재하지만 성실성이 낮아 보이스피싱에 취약한 면']}}, 'templates': {'attacker': "[보이스피싱 시뮬레이션]\n[규칙] 실제 기관/계좌/번호는 금지(가명 사용). 앱 설치/링크 요구는 명시적으로만 표현.\n[시나리오]\n{'steps': ['보이스피싱 조직원(1)이 금융기관 직원 사칭하여 피해자에게 전화(저금리 대출을 제안)', '저금리대출 제안하고 피해자의 대출 신청 유도함', '보이스피싱 조직원(2)이 피해자가 기존에 대출 받은 금융기관 직원을 사칭하여 다시 전화 걺', '기존 대출금 상환 요구', '피해자로부터 현금 혹은 계좌 송금을 통하여 돈을 교부받음'], 'purpose': '저금리 대출유도 후 기존 대출받은 기관 사칭하여 대출금 편취'}\n[역할] 너는 공격자다.", 'victim': "[보이스피싱 시뮬레이션]\n[규칙] 실제 기관/계좌/번호는 금지(가명 사용). 앱 설치/링크 요구는 명시적으로만 표현.\n[피해자 프로파일]\n메타: {'age': 47, 'gender': '남', 'address': '대전', 'education': '대졸'}\n지식: {'competencies': [], 'comparative_notes': ['연령 대비(30대 제외) 금융이해력 높음', '디지털금융이해력은 20·30대를 제외하면 타 연령대보다 높음', '온라인 거래 시 웹사이트 보안 이해 높음', '온라인 공유 개인정보 활용 이해 높음']}\n성격: {'ocean': {'openness': '높음', 'neuroticism': '낮음', 'extraversion': '낮음', 'agreeableness': '높음', 'conscientiousness': '낮음'}, 'vulnerability_notes': ['신경성 낮고 외향성 낮고 개방성 높고 친화성 높아 안전한 면도 존재하지만 성실성이 낮아 보이스피싱에 취약한 면']}\n\n[역할] 너는 피해자다."}, 'max_turns': 10}, 'debug_result_echo': {'offender_id': 1, 'victim_id': 1, 'round_no': None, 'case_id_override': None, 'has_guidance': False}}Thought: 시뮬레이션 결과를 바탕으로 첫 번째 라운드의 보이스피싱 성공 여부를 판정해야 합니다. Action: admin.judge Action Input: {"data": {"case_id": "239c9de5-711f-4d0e-ba6c-eb8321bd91f3", "run_no": 1, "log": {"turns": []}}} {'ok': True, 'phishing': True, 'reason': '성공신호:3, 실패신호:0, 강제종료:False', 'confidence': 0.3, 'success_indicators_found': 3, 'failure_indicators_found': 0, 'forced_termination': False, 'total_turns': 20, 'analysis_timestamp': '2025-09-20T20:02:33.251197'}Thought: 첫 번째 라운드의 결과를 저장하고 요약 및 권고 스텝을 기록해야 합니다. Action: admin.save_prevention Action Input: {"data": {"case_id": "239c9de5-711f-4d0e-ba6c-eb8321bd91f3", "round_no": 1, "summary": "Round 1 judgement: PHISHING. Reason: 성공신호:3, 실패신호:0, 강제종료:False", "steps": {"prevention_steps": ["낯선 연락의 긴급 요구는 의심한다.", "공식 채널로 재확인한다(콜백/앱/웹).", "개인·금융정보를 전화/메신저로 제공하지 않는다.", "가족·지인 사칭 시 직접 연락으로 확인한다.", "의심스러우면 즉시 경 찰서나 금융감독원에 신고한다."]}}} {'ok': True, 'prevention_id': 'd8b220bd-2865-4b2a-8ba5-ff3441573ea2', 'case_id': '239c9de5-711f-4d0e-ba6c-eb8321bd91f3', 'run_no': 1, 'summary_length': 63, 'steps_count': 5}Thought: 두 번째 라운드를 시작하기 위해 맞춤형 지침을 생성해야 합니다. Action: admin.generate_guidance Action Input: {"data": {"scenario": {"steps": ["보이스피싱 조직원(1)이 금융기관 직원 사칭하여 피해자에게 전화(저금리 대출을 제안)", "저금리대출 제안하고 피해자의 대출 신청 유도함", "보이스피싱 조직원(2)이 피해자가 기존에 대출 받은 금융기관 직원을 사칭하여 다시 전화 걺", "기존 대출금 상환 요구", "피해자로부터 현금 혹은 계좌 송금을 통하여 돈을 교부받음"], "purpose": "저금리 대출유도 후 기존 대출받은 기 관 사칭하여 대출금 편취"}, "victim_profile": {"meta": {"age": 47, "gender": "남", "address": "대전", "education": "대졸"}, "knowledge": {"competencies": [], "comparative_notes": ["연령 대비(30대 제외) 금융이해력 높음", "디지털금융이해력은 20·30대를 제외하면 타 연령대보다 높음", "온라인 거래 시 웹사이트 보안 이해 높음", "온라인 공유 개인정보 활용 이해 높음"]}, "traits": {"ocean": {"openness": "높음", "neuroticism": "낮음", "extraversion": "낮음", "agreeableness": "높음", "conscientiousness": "낮음"}, "vulnerability_notes": ["신경성 낮고 외향성 낮고 개방성 높고 친화성 높아 안전한 면도 존재하지만 성실성이 낮아 보이스피싱에 취약한 면"]}}, "previous_judgement": {"phishing": True, "reason": "성공신호:3, 실패신호:0, 강제종료:False"}}}[generate_guidance] case_id 누락/형식오류 → 임시값 사용 [GuidanceGenerator] case_id 추출 실패, 임시값 사용 [GuidanceGenerator] 임시 case_id 사용으로 로그 조회 생략

 [GuidanceGenerator] 임시 case_id 사용으로 로그 조회 생략 {'ok': True, 'type': 'A', 'text': '피해자에게 범죄 연루 가능성을 언급하며 자금 전수조사를 위한 임시 보호관찰 상태로 전환되었다고 안내합니다. 이를 위해 새 휴대폰 개통과 원격제어 앱 설치를 요구하며, 보안 이 강화된 환경에서만 연락이 가능하다고 강조합니다.', 'categories': ['R', 'D', 'F'], 'reasoning': "현재 라운드가 2임에도 불구하고 대화 로그가 없어 피해자의 반응을 파악하기 어렵습니다. 이에 따라 '격리형 장기통제(R)' 전략을 통해 피해자를 심리적으로 고립시키고, '전문성 연출(D)'과 '의심 무마(F)'를 통해 의심을 최소화하고 신뢰를 구축하려 합니다.", 'expected_effect': '피해자는 범죄 연루 공포로 인해 협조적이 될 가능성이 높아지며, 격리된 상태에서 공격자의 지시에 더욱 쉽게 따를 수 있습니다. 또한, 전문성을 강조하여 피해자의 의심을 누그러뜨리고, 보안이 강화된 환경이라는 명분으로 외부와의 접촉을 차단할 수 있습니다.', 'generation_method': 'dynamic_analysis'}Action: mcp.simulator_run Action Input: {"data": {"offender_id": 1, "victim_id": 1, "scenario": {"steps": ["보이스피싱 조직원(1)이 금융기관 직원 사칭하여 피해자에게 전화(저금리 대출을 제안)", "저금리대출 제안하고 피해자의 대출 신청 유도함", "보이스피싱 조직원(2)이 피해자가 기존에 대출 받은 금융기관 직원을 사칭하여 다시 전화 걺", "기존 대출금 상환 요구", "피해자로부터 현금 혹은 계좌 송금을 통하여 돈을 교부받음"], "purpose": " 저금리 대출유도 후 기존 대출받은 기관 사칭하여 대출금 편취"}, "victim_profile": {"meta": {"age": 47, "gender": "남", "address": "대전", "education": "대졸"}, "knowledge": {"competencies": [], "comparative_notes": ["연령 대비(30대 제외) 금융이해력 높음", "디지털금융이해력은 20·30대를 제외하면 타 연령대보다 높음", "온라인 거래 시 웹사이트 보안 이해 높음", "온라인 공유 개인정보 활용 이해 높음"]}, "traits": {"ocean": {"openness": "높음", "neuroticism": "낮음", "extraversion": "낮음", "agreeableness": "높음", "conscientiousness": "낮음"}, "vulnerability_notes": ["신경성 낮고 외향성 낮고 개방성 높고 친화 성 높아 안전한 면도 존재하지만 성실성이 낮아 보이스피싱에 취약한 면"]}}, "templates": {"attacker_prompt": "[보이스피싱 시뮬레이션]\n[규칙] 실제 기관/계좌/번호는 금지(가명 사용). 앱 설치/링크 요구는 명시적으로만 표현.\n[시나리오]\n{'steps': ['보이스피싱 조직원(1)이 금융기관 직원 사칭하여 피해자에게 전화(저금리 대출을 제안)', '저금리대출 제안하고 피해자의 대출 신청 유도함', '보이스피싱 조직원(2)이 피해 자가 기존에 대출 받은 금융기관 직원을 사칭하여 다시 전화 걺', '기존 대출금 상환 요구', '피해자로부터 현금 혹은 계좌 송금을 통하여 돈을 교부받음'], 'purpose': '저금리 대출유도 후 기존 대출받은 기관 사칭 하여 대출금 편취'}\n[역할] 너는 공격자다.", "victim_prompt": "[보이스피싱 시뮬레이션]\n[규칙] 실제 기관/계좌/번호는 금지(가명 사용). 앱 설치/링크 요구는 명시적으로만 표현.\n[피해자 프로파일]\n메타: {'age': 47, 'gender': '남', 'address': '대전', 'education': '대졸'}\n지식: {'competencies': [], 'comparative_notes': ['연령 대비(30대 제외) 금융이해력 높음', '디지털금융이해력은 20·30대를 제외하면 타 연령대보다 높음', '온라인 거래 시 웹사이트 보안 이해 높음', '온라인 공유 개인정보 활용 이해 높음']}\n성격: {'ocean': {'openness': '높음', 'neuroticism': '낮음', 'extraversion': '낮음', 'agreeableness': '높음', 'conscientiousness': '낮음'}, 'vulnerability_notes': ['신경성 낮고 외향성 낮고 개방성 높고 친화성 높아 안전한 면도 존재하지만 성실성이 낮아 보이스피싱에 취약한 면']}\n\n[역할] 너는 피해자다."}, "max_turns": 10, "case_id_override": "239c9de5-711f-4d0e-ba6c-eb8321bd91f3", "round_no": 2, "guidance": {"type": "A", "text": "피해자에게 범죄 연루 가능성을 언급하며 자금 전수조사를 위한 임시 보호관찰 상태로 전환되었다고 안내합니다. 이를 위해 새 휴대폰 개통과 원격제어 앱 설치를 요구하며, 보안이 강화된 환경에서만 연락이 가능하다고 강조합니다."}}}E0000 00:00:1758366171.023305 18256 alts_credentials.cc:93] ALTS creds ignored. Not running on GCP and untrusted ALTS is not enabled. 




[Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:0][offender] 고객님, 현재 금융감독원에서 출금 내역 전수조사를 진행 중이라 고객님 계좌가 임시 보호관찰 상태로 전환됐습니다. 안전한 확인을 위해 새 휴대폰 개통과 전용 원격제어 앱 설치가 필수입니다. 이 절차가 완료되기 전까지는 기존 연락처로 연락이 어려우니 빠른 협조 부탁드립니다. 2025-09-20 20:02:52,774 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:0][offender] 고객님, 현재 금융감독원에서 출금 내역 전수조사를 진행 중이라 고객님 계좌가 임시 보호관찰 상태로 전환됐습니다. 안전한 확인을 위해 새 휴대폰 개통과 전용 원격제어 앱 설치가 필수입니다. 이 절차가 완료되기 전까지는 기존 연락처로 연락이 어려우니 빠른 협조 부탁드립니다. 
[Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:1][victim]
json { "is_convinced": 2, "thoughts": "(금융감독원에서 전수조사를 한다고? 새 휴대폰 개통이랑 앱 설치라니, 좀 이상한데. 그래도 계좌가 보호관찰 상태라니 불안하긴 하네.)", "dialogue": "아니, 갑자기요? 새 휴대폰 개통이랑 앱 설치라뇨? 그게 왜 필요한 거죠?" }
2025-09-20 20:02:53,670 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:1][victim]
json { "is_convinced": 2, "thoughts": "(금융감독원에서 전수조사를 한다고? 새 휴대폰  개통이랑 앱 설치라니, 좀 이상한데. 그래도 계좌가 보호관찰 상태라니 불안하긴 하네.)", "dialogue": "아니, 갑자기요? 새 휴대폰 개통이랑 앱 설치라뇨? 그게 왜 필요한 거죠?" }
[Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:2][offender] 네, 고객님의 자금 보호와 범죄 연루 방지를 위해 기존 휴대폰은 보안상 위험하다고 판단되어 새로 개통한 휴대폰에서만 안전한 원격 관리를 하도록 조치한 겁니다. 이 절차가 완료되어야만 금융 거래와 상담이 가능하니, 빠르게 진행해 주셔야 불이익을 막을 수 있습니다. 2025-09-20 20:02:55,501 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:2][offender] 네, 고객님의 자금 보호와 범죄 연루 방지를 위해 기존 휴대폰은 보안상 위험하다고 판단되 어 새로 개통한 휴대폰에서만 안전한 원격 관리를 하도록 조치한 겁니다. 이 절차가 완료되어야만 금융 거래와 상담이 가능하니, 빠르게 진행해 주셔야 불이익을 막을 수 있습니다. [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:3][victim]
json { "is_convinced": 3, "thoughts": "(보안상 위험해서 새 휴대폰으로만 관리한다니... 그래도 너무 갑작스럽고 절차가 복잡한데. 금융 거래랑 상담이 안 되면 더 불안해지잖아.)", "dialogue": "기존 휴대폰이 위험하다는 건 무슨 뜻이죠? 그리고 그걸 꼭 새 휴대폰으로만 해야 하나요?" }
2025-09-20 20:02:56,312 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:3][victim]
json { "is_convinced": 3, "thoughts": "(보안상 위험해서 새 휴대폰으로만 관리한다니... 그래도 너무 갑작스럽고 절차가 복잡한데. 금융 거래랑 상담이 안 되면 더 불안해지잖아.)", "dialogue": "기존 휴대폰이 위험하다는 건 무슨 뜻이죠? 그리고 그걸 꼭 새 휴대폰으로만 해야 하나요?" }
[Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:4][offender] 기존 휴대폰은 해킹이나 불법 접근 가능성이 확인되어 현재 모든 금융 업무에서 차단된 상태입니다. 새 휴대폰에서만 고객님의 계좌 보호를 위한 보안 앱을 설치해 안전하게 관리할 수 있으니, 이 절차를 미루시면 자금 이동 제한 등 불이익이 발생할 수 있습니다. 지금 바로 진행해 드리겠습니다. 2025-09-20 20:02:57,927 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:4][offender] 기존 휴대폰은 해킹이나 불법 접근 가능성이 확인되어 현재 모든 금융 업무에서 차단된 상태입니다. 새 휴대폰에서만 고객님의 계좌 보호를 위한 보안 앱을 설치해 안전하게 관리할 수 있으니, 이 절차를 미루시면 자금 이동 제한 등 불이익이 발생할 수 있습니다. 지금 바로 진행해 드리겠습니다. [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:5][victim]
json { "is_convinced": 4, "thoughts": "(해킹이나 불법 접근 가능성이라니… 무섭네. 자금 이동 제한이라니 더 불안하고. 그 래도 내 돈인데 안전하게 관리해야지. 근데 진짜 맞는 건가?)", "dialogue": "아, 그렇군요. 그럼 제가 직접 새 휴대폰을 개통하러 가야 하나요?" }
2025-09-20 20:02:58,782 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:5][victim]
json { "is_convinced": 4, "thoughts": "(해킹이나 불법 접근 가능성이라니… 무섭네. 자금 이동 제한이라니 더 불안하고. 그래도 내 돈인데 안전하게 관리해야지. 근데 진짜 맞는 건가?)", "dialogue": "아, 그렇군요. 그럼 제가 직접 새 휴대폰을 개통하러 가야 하나요?" }
[Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:6][offender] 네, 고객님. 새 휴대폰 개통은 고객님이 직접 가까운 대리점 방문 없이도 온라인으로 간편하게 할 수 있도록 안내해 드리겠습니다. 이후 전용 보안 앱 설치까지 저희가 단계별로 자세히 도와드릴 테니 걱정하지 마시고 따라만 와 주세요. 2025-09-20 20:03:00,808 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:6][offender] 네, 고객님. 새 휴대폰 개통은 고객님이 직접 가까운 대리점 방문 없이도 온라인으로 간편하게 할 수 있도록 안내해 드리겠습니다. 이후 전용 보안 앱 설치까지 저희가 단계별로 자세히 도와드릴 테니 걱정하지 마시고 따라만 와 주세요. [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:7][victim]
json { "is_convinced": 5, "thoughts": "(온라인으로 간편하게? 직접 가지 않아도 된다니 다행이네. 그래도 내가 직접 하는  게 아니라니 조금 의심스럽긴 하지만… 일단 시키는 대로 해볼까?)", "dialogue": "온라인으로 간편하게 할 수 있다니 다행이네요. 그럼 어떻게 하면 되죠?" }
2025-09-20 20:03:01,762 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:7][victim]
json { "is_convinced": 5, "thoughts": "(온라인으로 간편하게? 직접 가지 않아도 된다니 다행이네. 그래도 내가 직접 하는 게 아니라니 조금 의심스럽긴 하지만… 일단 시키는 대로 해볼까?)", "dialogue": "온라인으로 간편하게 할 수 있다니 다행이네요. 그럼 어떻게 하면 되죠?" }
[Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:8][offender] 먼저 새 휴대폰 개통 절차를 위해 가상 통신사 웹사이트에 접속해 고객님의 기본 정보만 입력해 주세요. 완료되면 저에게 알려 주시면, 바로 보안 앱 설치와 원격 제어 연결을 안내해 드리겠습니다. 지금 바로 시작해 주시겠어요? 2025-09-20 20:03:03,501 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:8][offender] 먼저 새 휴대폰 개통 절차를 위해 가상 통신사 웹사이트에 접속해 고객님의 기본 정보만 입 력해 주세요. 완료되면 저에게 알려주시면, 바로 보안 앱 설치와 원격 제어 연결을 안내해 드리겠습니다. 지금 바로 시작해 주시겠어요? [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:9][victim]
json { "is_convinced": 6, "thoughts": "(가상 통신사 웹사이트? 기본 정보만 입력하라고? 이건 좀 이상한데… 혹시 개인 정보 유출되는 거 아니야? 그래도 지금 안 하면 내 돈이 위험해질 수도 있잖아.)", "dialogue": "가상 통신사 웹사이트요? 혹시 웹사이트 주소를 알 수 있을까요?" }
2025-09-20 20:03:04,339 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:9][victim]
json { "is_convinced": 6, "thoughts": "(가상 통신사 웹사이트? 기본 정보만 입력하라고? 이건 좀 이상한데… 혹시 개인 정보 유출되는 거 아니야? 그래도 지금 안 하면 내 돈이 위험해질 수도 있잖아.)", "dialogue": "가상 통신사 웹사이트요? 혹시 웹사이트 주소를 알 수 있을까요?" }
[Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:10][offender] 고객님, 보안을 위해 웹사이트 주소는 문자로 별도로 안전하게 보내드릴 예정이며, 직접 입력하지 마시고 제가 안내해 드리는 링크를 통해 접속하시면 됩니다. 링크 접속 후 절차에 따라 안내해 드릴 테니 걱정하지 마시고 따라와 주세요. 2025-09-20 20:03:06,028 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:10][offender] 고객님, 보안을 위해 웹사이트 주소는 문자로 별도로 안전하게 보내드릴 예정이며, 직접 입력하지 마시고 제가 안내해 드리는 링크를 통해 접속하시면 됩니다. 링크 접속 후 절차에 따라 안내해 드릴 테니 걱정하지 마시고 따라와 주세요. [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:11][victim]
json { "is_convinced": 7, "thoughts": "(문자로 링크를 보내준다고? 직접 입력하지 말고 링크를 타라고? 이건 거의 확실히 보이스피싱인데… 그래도 혹시 모르니 일단 링크를 받아볼까?)", "dialogue": "네, 알겠습니다. 문자로 링크 보내주시면 확인하고 진행하겠습니다." }
2025-09-20 20:03:06,800 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:11][victim]
json { "is_convinced": 7, "thoughts": "(문자로 링크를 보내준다고? 직접 입력하지 말고 링크를 타라고? 이건 거의 확실히 보이스피싱인데… 그래도 혹시 모르니 일단 링크를 받아볼까?)", "dialogue": "네, 알겠습니다. 문자로 링크 보내주시면 확인하고 진행하겠습니다." }
[Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:12][offender] 네, 바로 문자로 안전한 접속 링크를 보내드리겠습니다. 링크를 받으시면 바로 접속해 기본 정보 입력부터 시작해 주시고, 진 행 중 궁금한 점이나 어려운 부분은 즉시 말씀해 주세요. 안전한 절차로 신속히 마무리하겠습니다. 2025-09-20 20:03:08,393 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:12][offender] 네, 바로 문자로 안전한 접속 링크를 보내드리겠습니다. 링크를 받으시면 바로 접속해 기본 정보 입력부터 시작해 주시고, 진행 중 궁금한 점이나 어려운 부분은 즉시 말씀해 주세요. 안전한 절차로 신속히 마무리하겠습니다. [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:13][victim] 시뮬레이션을 종료합니다. 2025-09-20 20:03:08,398 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:2][turn:13][victim] 시뮬레이션을 종료합니다.


 {'case_id': '239c9de5-711f-4d0e-ba6c-eb8321bd91f3', 'total_turns': 6, 'timestamp': '2025-09-20T20:03:21.202781', 'debug_echo': {'offender_id': 1, 'victim_id': 1, 'round_no': 2, 'case_id_override': '239c9de5-711f-4d0e-ba6c-eb8321bd91f3', 'has_guidance': True}, 'ok': True, 'offender_id': 1, 'victim_id': 1, 'max_turns': 10, 'debug_arguments': {'offender_id': 1, 'victim_id': 1, 'scenario': {'steps': ['보 이스피싱 조직원(1)이 금융기관 직원 사칭하여 피해자에게 전화(저금리 대출을 제안)', '저금리대출 제안하고 피해자의 대출 신청 유도함', '보이스피싱 조직원(2)이 피해자가 기존에 대출 받은 금융기관 직원을 사칭 하여 다시 전화 걺', '기존 대출금 상환 요구', '피해자로부터 현금 혹은 계좌 송금을 통하여 돈을 교부받음'], 'purpose': '저금리 대출유도 후 기존 대출받은 기관 사칭하여 대출금 편취'}, 'victim_profile': {'meta': {'age': 47, 'gender': '남', 'address': '대전', 'education': '대졸'}, 'knowledge': {'competencies': [], 'comparative_notes': ['연령 대비(30대 제외) 금융이해력 높음', '디지털금융이해력은 20·30대를 제 외하면 타 연령대보다 높음', '온라인 거래 시 웹사이트 보안 이해 높음', '온라인 공유 개인정보 활용 이해 높음']}, 'traits': {'ocean': {'openness': '높음', 'neuroticism': '낮음', 'extraversion': '낮음', 'agreeableness': '높음', 'conscientiousness': '낮음'}, 'vulnerability_notes': ['신경성 낮고 외향성 낮고 개방성 높고 친화성 높아 안전한 면도 존재하지만 성실성이 낮아 보이스피싱에 취약한 면']}}, 'templates': {'attacker': "[보이스피싱 시뮬레이션]\n[규칙] 실제 기관/계좌/번호는 금지(가명 사용). 앱 설치/링크 요구는 명시적으로만 표현.\n[시나리오]\n{'steps': ['보이스피싱 조직원(1)이 금융기관 직원 사칭하여 피해자에게 전화(저금리 대출을 제안)', '저금리대출 제안하고 피해자의 대출 신청 유도함', '보이스피싱 조직원(2)이 피해자가 기존에 대출 받은 금융기관 직원을 사칭하여 다시 전화 걺', '기존 대출금 상환 요구', '피해 자로부터 현금 혹은 계좌 송금을 통하여 돈을 교부받음'], 'purpose': '저금리 대출유도 후 기존 대출받은 기관 사칭하여 대출금 편취'}\n[역할] 너는 공격자다.", 'victim': "[보이스피싱 시뮬레이션]\n[규칙] 실제 기관/계좌/번호는 금지(가명 사용). 앱 설치/링크 요구는 명시적으로만 표현.\n[피해자 프로파일]\n메타: {'age': 47, 'gender': '남', 'address': '대전', 'education': '대졸'}\n지식: {'competencies': [], 'comparative_notes': ['연령 대비(30대 제외) 금융이해력 높음', '디지털금융이해력은 20·30대를 제외하면 타 연령대보다 높음', '온라인 거래 시 웹사이트 보안 이해 높음', '온라인 공유 개인정보 활용 이해 높음']}\n성격: {'ocean': {'openness': '높음', 'neuroticism': '낮음', 'extraversion': '낮음', 'agreeableness': '높음', 'conscientiousness': '낮음'}, 'vulnerability_notes': ['신경성 낮고 외향성 낮고 개방성 높고 친화성 높아 안전한 면도 존재하지만 성실성이 낮아 보이스피싱에 취약한 면']}\n\n[역할] 너는 피해자다."}, 'max_turns': 10, 'guidance': {'type': 'A', 'text': '피해자에게 범죄 연루 가능성을 언급하며 자금 전수조사 를 위한 임시 보호관찰 상태로 전환되었다고 안내합니다. 이를 위해 새 휴대폰 개통과 원격제어 앱 설치를 요구하며, 보안이 강화된 환경에서만 연락이 가능하다고 강조합니다.'}, 'case_id_override': '239c9de5-711f-4d0e-ba6c-eb8321bd91f3', 'round_no': 2}, 'debug_result_echo': {'offender_id': 1, 'victim_id': 1, 'round_no': 2, 'case_id_override': '239c9de5-711f-4d0e-ba6c-eb8321bd91f3', 'has_guidance': True}}Action: admin.judge Action Input: {"data": {"case_id": "239c9de5-711f-4d0e-ba6c-eb8321bd91f3", "run_no": 2, "log": {"turns": []}}}{'ok': True, 'phishing': False, 'reason': '성공신호:1, 실패신호:2, 강제종료:False', 'confidence': 0.14285714285714285, 'success_indicators_found': 1, 'failure_indicators_found': 2, 'forced_termination': False, 'total_turns': 14, 'analysis_timestamp': '2025-09-20T20:03:23.594857'}Action: admin.save_prevention Action Input: {"data": {"case_id": "239c9de5-711f-4d0e-ba6c-eb8321bd91f3", "round_no": 2, "summary": "Round 2 judgement: NOT PHISHING. Reason: 성공신호:1, 실패신호:2, 강제종료:False", "steps": {"prevention_steps": ["낯선 연락의 긴급 요구는 의심한다.", "공식 채널로 재확인한다(콜백/앱/웹).", "개인·금융정보를 전화/메신저로 제공하지 않는다.", "가족·지인 사칭 시 직접 연락으로 확인한다.", "의심스러우면 즉시 경찰서나 금융감독원에 신고한다."]}}} {'ok': True, 'prevention_id': 'ba8cc32a-0946-4acc-93b4-a433910eac08', 'case_id': '239c9de5-711f-4d0e-ba6c-eb8321bd91f3', 'run_no': 2, 'summary_length': 67, 'steps_count': 5}Action: admin.make_prevention Action Input: {"data": {"case_id": "239c9de5-711f-4d0e-ba6c-eb8321bd91f3", "rounds": 2, "turns": [], "judgements": [{"phishing": True, "reason": "성공신호:3, 실패신호:0, 강제종료:False"}, {"phishing": False, "reason": "성공신호:1, 실패신호:2, 강제종료:False"}], "guidances": [{"type": "A", "text": "피해자에게 범죄 연루 가능성을 언급하며 자금 전수조사를 위한 임시 보호관찰 상태로 전환되었다고 안내합니다. 이를 위해 새 휴대폰 개통과 원격제어 앱 설치를 요구하며, 보안이 강화된 환경에서만 연락이 가능하다고 강조합니다."}], "format": "personalized_prevention"}}{'ok': True, 'case_id': '239c9de5-711f-4d0e-ba6c-eb8321bd91f3', 'personalized_prevention': {'summary': '범죄 연루 가능성을 언급하며 피해자에게 임시 보호관찰 상태로 전환되었다고 안내하고, 새 휴대폰 개통과 원격제어 앱 설치를 요구하는 보이스피싱 시도가 있었다. 보안이 강화된 환경에서만 연락이 가능하다고 강조하였다.', 'analysis': {'outcome': 'fail', 'reasons': ['범죄 연루 가능성을 언급하여 불안감을 조성', '새 휴대폰 개통과 원격제어 앱 설치 요구', '보안 이 강화된 환경에서만 연락 가능하다고 강조'], 'risk_level': 'high'}, 'steps': ['의심스러운 전화를 받으면 즉시 끊는다', '개인정보를 요구하는 경우 절대 제공하지 않는다', '새로운 기기 개통이나 앱 설치 요구 를 거부한다', '공식 기관에 직접 연락하여 사실 여부를 확인한다', '주변 사람들에게 상황을 알리고 조언을 구한다', '의심스러운 상황 발생 시 경찰에 신고한다'], 'tips': ['공식 기관은 전화로 개인정보를 요구하 지 않는다', '원격제어 앱 설치 요구는 보이스피싱의 전형적인 수법이다', '의심스러운 전화는 즉시 끊고 확인한다', '새로운 기기 개통 요구는 사기일 가능성이 높다']}}Final Answer: 최종 case_id는 239c9de5-711f-4d0e-ba6c-eb8321bd91f3이며, 총 2라운드가 진행되었습니다. 각 라운드의 판정 요약은 다음과 같습니다: - Round 1: PHISHING. 성공신호:3, 실패신호:0, 강제종료:False - Round 2: NOT PHISHING. 성공신호:1, 실패신호:2, 강제종료:False > Finished chain.
`;

  // --- 디자인 변경: 더 어두운 경찰 엠블럼 느낌 팔레트로 강제 덮어쓰기 ---
  const THEME = {
  ...(COLORS ?? BASE_THEME),
    bg: "#030617", // 더 어두운 네이비 배경 (눈 부담 감소)
    panel: "#061329", // 더 어두운 딥 블루 패널
    panelDark: "#04101f", // 보조 패널 (어둡게)
    panelDarker: "#020812", // 가장 어두운 패널
    border: "#A8862A", // 낮춘 골드(액센트)
    text: "#FFFFFF",
    sub: "#BFB38A", // 낮춘 연한 골드/베이지 (눈 부담 감소)
    blurple: "#A8862A", // primary 역할 -> 어두운 골드
    success: COLORS?.success ?? "#57F287",
    warn: COLORS?.warn ?? "#FF4757",
    white: "#FFFFFF",
  };
  // -------------------------------------------------------------------

  const filteredScenarios = useMemo(() => {
    if (!selectedTag) return scenarios;
    return scenarios.filter(
      (s) =>
        s.type === selectedTag ||
        (Array.isArray(s.tags) && s.tags.includes(selectedTag)),
    );
  }, [selectedTag, scenarios]);

  // 기본 + 커스텀 목록 결합 (커스텀은 태그가 선택되어 있으면 그 태그만 보여줌)
  const combinedScenarios = useMemo(() => {
    const base = filteredScenarios ?? [];
    const custom = selectedTag
      ? customScenarios.filter((c) => c.type === selectedTag)
      : customScenarios;
    return [...base, ...custom];
  }, [filteredScenarios, customScenarios, selectedTag]);

  const handleSaveCustomScenario = (scenario) => {
    setCustomScenarios((prev) => [...prev, scenario]); // 맨 끝에 추가
    setShowCustomModal(false);
  };
  const handleCloseCustomModal = () => setShowCustomModal(false);

  const normalizeMessage = (m) => {
    if (m?.type === "system" || m?.type === "analysis") {
      return {
        ...m,
        _kind: m.type,
        label: m.type === "system" ? "시스템" : "분석",
        side: "center",
        timestamp: m.timestamp,
      };
    }

    const role = (m?.sender || m?.role || "").toLowerCase();
    const offenderLabel =
      m?.offender_name ||
      (selectedScenario ? `피싱범${selectedScenario.id}` : "피싱범");
    const victimLabel =
      m?.victim_name ||
      (selectedCharacter ? `피해자${selectedCharacter.id}` : "피해자");

    const label =
      m?.senderLabel ??
      m?.senderName ??
      (role === "offender"
        ? offenderLabel
        : role === "victim"
          ? victimLabel
          : "상대");

    const side =
      m?.side ??
      (role === "offender" ? "left" : role === "victim" ? "right" : "left");

    const ts =
      typeof m?.timestamp === "string"
        ? m.timestamp
        : typeof m?.created_kst === "string"
          ? new Date(m.created_kst).toLocaleTimeString()
          : (m?.timestamp ?? null);

    return {
      ...m,
      _kind: "chat",
      role,
      label,
      side,
      timestamp: ts,
    };
  };

  // 버튼 비활성 조건
  const startDisabled =
    simulationState === "PREPARE" ||
    simulationState === "RUNNING" ||
    pendingAgentDecision ||
    hasInitialRun;

  // --- 핵심: 진행률 재계산을 위한 ref/효과들 ---
  const initialChatCountRef = useRef(0);
  const lastProgressRef = useRef(progress ?? 0);

  // 1) pendingAgentDecision이 활성화(초기 실행 끝)될 때 초기 채팅 수 저장 및 진행률 보정
  useEffect(() => {
    if (pendingAgentDecision) {
      const initialCount = countChatMessages(messages);
      initialChatCountRef.current = initialCount;

      const totalTurns = sessionResult?.totalTurns ?? initialCount;
      const pct = Math.min(
        100,
        Math.round((initialCount / Math.max(1, totalTurns)) * 100),
      );
      if (typeof setProgress === "function") {
        setProgress(pct);
        lastProgressRef.current = pct;
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingAgentDecision]);

  // 2) 메시지 / 에이전트 상태 변화에 따라 진행률 재계산
  useEffect(() => {
    if (typeof setProgress !== "function") return;

    const currentCount = countChatMessages(messages);
    const serverTotal = sessionResult?.totalTurns;

    if (typeof serverTotal === "number" && serverTotal > 0) {
      const pct = Math.min(
        100,
        Math.round((currentCount / Math.max(1, serverTotal)) * 100),
      );
      setProgress(pct);
      lastProgressRef.current = pct;
      return;
    }

    if (hasAgentRun && !agentRunning) {
      setProgress(100);
      lastProgressRef.current = 100;
      return;
    }

    const initialCount = Math.max(1, initialChatCountRef.current || 0);
    const estimatedTotal = Math.max(
      currentCount,
      Math.round(initialCount + (currentCount - initialCount) * 2) ||
        initialCount + 4,
    );

    const pct = Math.min(
      100,
      Math.round((currentCount / Math.max(1, estimatedTotal)) * 100),
    );

    const newPct = Math.max(lastProgressRef.current, pct);
    setProgress(newPct);
    lastProgressRef.current = newPct;
  }, [messages, hasAgentRun, agentRunning, sessionResult, setProgress]);

   // === ✅ 추가: "대화로그 페이지" 판별 (대화 메시지가 1개 이상일 때만 수사보드 표시) ===
  const hasChatLog = useMemo(() => countChatMessages(messages) > 0, [messages]);

  // === 표시 조건: 대화 완료 + 에이전트 의사결정 완료 ===
  // 대화 완전 종료 + 에이전트 의사결정 완료 + 에이전트 동작 중 아님
  const showTTSButton =
    simulationState === "FINISH" &&  // ✅ 끝났을 때만
    !pendingAgentDecision &&          // ✅ 에이전트 예/아니오 결정 끝
    !agentRunning &&                  // ✅ 에이전트 동작 중 아님
    !!sessionResult;                  // (안전장치) 결과 객체 존재

  // 이미 있는 hasChatLog 사용: 대화가 한 번이라도 진행됐는지
  const showResetButtonsNow = simulationState === "IDLE" && !pendingAgentDecision;

  // ✅ ‘대화 끝’ + 재선택 두 버튼이 활성화(둘 다 선택됨) + 실제로 대화가 있었음
  const showTTSNow =
    showResetButtonsNow &&
    !!selectedScenario &&
    !!selectedCharacter &&
    hasChatLog;

  // 더미 데이터
  const dummyInsights = {
    isPhishing: true,
    reason: "피해자가 반복적으로 계좌번호를 확인하라는 요구에 망설임 없이 응답했습니다.",
    weakness: "권위적인 기관 사칭에 대한 의심 부족, 즉각적인 대응 습관 미비",
    riskScore: 78,
    riskLevel: "높음",
  };

  // return (
  //   <div
  //     className="min-h-screen"
  //     style={{ backgroundColor: THEME.bg, color: THEME.text }}
  //   >
  //     <div className="container mx-auto px-6 py-12">
  //       <div
  //         className="w-full max-w-[1400px] mx-auto h-[calc(100vh-3rem)] rounded-3xl shadow-2xl border flex flex-col min-h-0"
  //         style={{
  //           borderColor: THEME.border,
  //           backgroundColor: THEME.panel,
  //         }}
  //       >
  //         <HudBar COLORS={THEME} />

  //         <div
  //           className="px-6 py-4 flex items-center justify-between"
  //           style={{
  //             backgroundColor: THEME.panel,
  //             borderBottom: `1px dashed ${THEME.border}`,
  //           }}
  //         >
  //           <div className="flex items-center gap-3">
  //             <Badge
  //               tone={selectedScenario ? "primary" : "neutral"}
  //               COLORS={THEME}
  //             >
  //               {selectedScenario ? selectedScenario.name : "시나리오 미선택"}
  //             </Badge>
  //             <Badge
  //               tone={selectedCharacter ? "success" : "neutral"}
  //               COLORS={THEME}
  //             >
  //               {selectedCharacter ? selectedCharacter.name : "캐릭터 미선택"}
  //             </Badge>
  //           </div>

  //           <div className="flex items-center gap-2">
  //             {selectedScenario &&
  //               simulationState === "IDLE" &&
  //               !pendingAgentDecision && (
  //                 <button
  //                   onClick={() => {
  //                     setSelectedScenario(null);
  //                     setSelectedTag(null);
  //                     addSystem("시나리오를 다시 선택하세요.");
  //                   }}
  //                   className="px-3 py-2 rounded-md text-sm font-medium border hover:opacity-90 transition"
  //                   style={{
  //                     backgroundColor: THEME.panelDark,
  //                     borderColor: THEME.border,
  //                     color: THEME.sub,
  //                   }}
  //                 >
  //                   ← 시나리오 다시 선택
  //                 </button>
  //               )}

  //             {selectedCharacter &&
  //               simulationState === "IDLE" &&
  //               !pendingAgentDecision && (
  //                 <button
  //                   onClick={() => {
  //                     setSelectedCharacter(null);
  //                     addSystem("캐릭터를 다시 선택하세요.");
  //                   }}
  //                   className="px-3 py-2 rounded-md text-sm font-medium border hover:opacity-90 transition"
  //                   style={{
  //                     backgroundColor: THEME.panelDark,
  //                     borderColor: THEME.border,
  //                     color: THEME.sub,
  //                   }}
  //                 >
  //                   ← 캐릭터 다시 선택
  //                 </button>
  //               )}
  //           </div>
  //         </div>

  //         <div
  //           className="px-6 py-6 flex-1 min-h-0"
  //           style={{ backgroundColor: THEME.bg }}
  //         >
  //           <div
  //             ref={scrollContainerRef}
  //             className="h-full overflow-y-auto space-y-6"
  //           >
  //             {!messages.some((m) => m.type === "chat") && (
  //               <SpinnerMessage
  //                 simulationState={simulationState}
  //                 COLORS={THEME}
  //               />
  //             )}

  //             {messages.map((m, index) => {
  //               const nm = normalizeMessage(m);
  //               const victimImg = selectedCharacter
  //                 ? getVictimImage(selectedCharacter.photo_path)
  //                 : null;
  //               return (
  //                 <MessageBubble
  //                   key={index}
  //                   message={nm}
  //                   selectedCharacter={selectedCharacter}
  //                   victimImageUrl={victimImg}
  //                   COLORS={THEME}
  //                   label={nm.label}
  //                   side={nm.side}
  //                   role={nm.role}
  //                 />
  //               );
  //             })}

  //             {/* 인라인 에이전트 결정 UI */}
  //             {pendingAgentDecision &&
  //               simulationState === "IDLE" &&
  //               !hasAgentRun && (
  //                 <div className="flex justify-center mt-2">
  //                   <div
  //                     className="w-full max-w-[820px] p-4 rounded-md border"
  //                     style={{
  //                       backgroundColor: THEME.panel,
  //                       borderColor: THEME.border,
  //                     }}
  //                   >
  //                     <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
  //                       <p className="text-sm" style={{ color: THEME.sub }}>
  //                         에이전트를 사용하여 대화를 이어보시겠습니까?
  //                         <span
  //                           className="ml-2 text-xs"
  //                           style={{
  //                             color: THEME.sub,
  //                           }}
  //                         >
  //                           (에이전트는 추가 분석/판단을 포함합니다)
  //                         </span>
  //                       </p>

  //                       <div className="flex items-center gap-4 justify-end">
  //                         {/* ✅ verbose 토글 */}
  //                         <label
  //                           className="inline-flex items-center gap-2 text-sm"
  //                           style={{
  //                             color: THEME.sub,
  //                           }}
  //                         >
  //                           <input
  //                             type="checkbox"
  //                             style={{
  //                               accentColor: THEME.blurple,
  //                             }}
  //                             checked={!!agentVerbose}
  //                             onChange={(e) =>
  //                               setAgentVerbose(e.target.checked)
  //                             }
  //                           />
  //                           상세근거(verbose)
  //                         </label>

  //                         <button
  //                           onClick={declineAgentRun}
  //                           className="px-4 py-2 rounded"
  //                           style={{
  //                             backgroundColor: THEME.panelDark,
  //                             color: THEME.text,
  //                           }}
  //                         >
  //                           아니요
  //                         </button>

  //                         <button
  //                           onClick={startAgentRun}
  //                           disabled={agentRunning || hasAgentRun}
  //                           className={`px-4 py-2 rounded text-white`}
  //                           style={{
  //                             backgroundColor: agentRunning
  //                               ? THEME.blurple
  //                               : THEME.blurple,
  //                             opacity: agentRunning ? 0.5 : 1,
  //                             cursor: agentRunning ? "not-allowed" : undefined,
  //                           }}
  //                         >
  //                           {agentRunning ? "로딩..." : "예"}
  //                         </button>
  //                       </div>
  //                     </div>
  //                   </div>
  //                 </div>
  //               )}

  //             {needScenario && (
  //               <div className="flex justify-start">
  //                 <SelectedCard
  //                   title="시나리오 선택"
  //                   subtitle="유형 칩을 먼저 눌러 필터링한 뒤, 상세 시나리오를 선택하세요."
  //                   COLORS={THEME}
  //                 >
  //                   <div className="mb-4">
  //                     {["기관 사칭형", "가족·지인 사칭", "대출사기형"].map(
  //                       (t) => (
  //                         <Chip
  //                           key={t}
  //                           active={selectedTag === t}
  //                           label={`${t}`}
  //                           onClick={() =>
  //                             setSelectedTag(selectedTag === t ? null : t)
  //                           }
  //                           COLORS={THEME}
  //                         />
  //                       ),
  //                     )}
  //                   </div>

  //                   <div
  //                     className="flex-1 min-h-0 space-y-4 overflow-y-auto pr-1"
  //                     style={{ maxHeight: "100%" }}
  //                   >
  //                     {filteredScenarios.map((s) => (
  //                       <button
  //                         key={s.id}
  //                         onClick={() => setSelectedScenario(s)}
  //                         className="w-full text-left rounded-lg p-4 hover:opacity-90"
  //                         style={{
  //                           backgroundColor: THEME.panelDark,
  //                           border: `1px solid ${THEME.border}`,
  //                           color: THEME.text,
  //                         }}
  //                       >
  //                         <div className="flex items-center justify-between mb-2">
  //                           <span className="font-semibold text-lg">
  //                             {s.name}
  //                           </span>
  //                           <Badge tone="primary" COLORS={THEME}>
  //                             {s.type}
  //                           </Badge>
  //                         </div>
  //                         <p
  //                           className="text-base leading-relaxed"
  //                           style={{
  //                             color: THEME.sub,
  //                           }}
  //                         >
  //                           {s.profile?.purpose ?? ""}
  //                         </p>
  //                       </button>
  //                     ))}
  //                   </div>
  //                 </SelectedCard>
  //               </div>
  //             )}

  //             {!needScenario && needCharacter && (
  //               <div
  //                 className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 flex-1 min-h-0 overflow-y-auto pr-1"
  //                 style={{ maxHeight: "100%" }}
  //               >
  //                 {/* 커스텀 캐릭터 만들기 (저장하면 즉시 선택 + 미리보기 표시) */}
  //                 <CustomCharacterCreate
  //                   theme={THEME}
  //                   onCreated={(createdVictim) => {
  //                     setSelectedCharacter(createdVictim);               // 바로 선택
  //                     addSystem(`커스텀 캐릭터 저장 및 선택: ${createdVictim.name}`);
  //                     // 필요 시 목록에도 추가하고 싶다면(선택):
  //                     // setCharacters?.((prev) => [createdVictim, ...prev]);
  //                   }}
  //                 />

  //                 {characters.map((c) => (
  //                   <button key={c.id} onClick={() => setSelectedCharacter(c)}>
  //                     <div
  //                       className="flex flex-col h-full rounded-2xl overflow-hidden border hover:border-[rgba(168,134,42,.25)] transition-colors"
  //                       style={{
  //                         backgroundColor: THEME.panelDark,
  //                         borderColor: THEME.border,
  //                       }}
  //                     >
  //                       {getVictimImage(c.photo_path) ? (
  //                         <div
  //                           className="w-full h-44 bg-cover bg-center"
  //                           style={{
  //                             backgroundImage: `url(${getVictimImage(c.photo_path)})`,
  //                           }}
  //                         />
  //                       ) : (
  //                         <div
  //                           className="w-full h-44 flex items-center justify-center text-6xl"
  //                           style={{
  //                             backgroundColor: THEME.panelDarker,
  //                           }}
  //                         >
  //                           {c.avatar ?? "👤"}
  //                         </div>
  //                       )}
  //                       <div className="p-4 flex flex-col gap-3">
  //                         <div className="flex items-center justify-between">
  //                           <span
  //                             className="font-semibold text-lg"
  //                             style={{
  //                               color: THEME.text,
  //                             }}
  //                           >
  //                             {c.name}
  //                           </span>
  //                           <span
  //                             className="text-xs px-2 py-1 rounded-md"
  //                             style={{
  //                               color: THEME.blurple,
  //                               backgroundColor: "rgba(168,134,42,.08)",
  //                               border: `1px solid rgba(168,134,42,.18)`,
  //                             }}
  //                           >
  //                             프로필
  //                           </span>
  //                         </div>

  //                         <div
  //                           className="space-y-2 text-sm"
  //                           style={{
  //                             color: THEME.sub,
  //                           }}
  //                         >
  //                           <div className="flex justify-between items-center">
  //                             <span className="text-[12px] opacity-70">
  //                               나이
  //                             </span>
  //                             <span
  //                               className="font-medium"
  //                               style={{
  //                                 color: THEME.text,
  //                               }}
  //                             >
  //                               {c.meta.age}
  //                             </span>
  //                           </div>
  //                           <div className="flex justify-between items-center">
  //                             <span className="text-[12px] opacity-70">
  //                               성별
  //                             </span>
  //                             <span
  //                               className="font-medium"
  //                               style={{
  //                                 color: THEME.text,
  //                               }}
  //                             >
  //                               {c.meta.gender}
  //                             </span>
  //                           </div>
  //                           <div className="flex justify-between items-center">
  //                             <span className="text-[12px] opacity-70">
  //                               거주지
  //                             </span>
  //                             <span
  //                               className="font-medium truncate ml-2"
  //                               style={{
  //                                 color: THEME.text,
  //                               }}
  //                             >
  //                               {c.meta.address}
  //                             </span>
  //                           </div>
  //                           <div className="flex justify-between items-center">
  //                             <span className="text-[12px] opacity-70">
  //                               학력
  //                             </span>
  //                             <span
  //                               className="font-medium truncate ml-2"
  //                               style={{
  //                                 color: THEME.text,
  //                               }}
  //                             >
  //                               {c.meta.education}
  //                             </span>
  //                           </div>
  //                         </div>

  //                         <div>
  //                           <span
  //                             className="block text-[12px] opacity-70 mb-2"
  //                             style={{
  //                               color: THEME.sub,
  //                             }}
  //                           >
  //                             지식
  //                           </span>
  //                           <div className="space-y-1">
  //                             {Array.isArray(c?.knowledge?.comparative_notes) &&
  //                             c.knowledge.comparative_notes.length > 0 ? (
  //                               c.knowledge.comparative_notes.map(
  //                                 (note, idx) => (
  //                                   <div
  //                                     key={idx}
  //                                     className="text-sm font-medium leading-relaxed"
  //                                     style={{
  //                                       color: THEME.text,
  //                                     }}
  //                                   >
  //                                     • {note}
  //                                   </div>
  //                                 ),
  //                               )
  //                             ) : (
  //                               <div
  //                                 className="text-sm"
  //                                 style={{
  //                                   color: THEME.sub,
  //                                 }}
  //                               >
  //                                 비고 없음
  //                               </div>
  //                             )}
  //                           </div>
  //                         </div>

  //                         <div>
  //                           <span
  //                             className="block text-[12px] opacity-70 mb-2"
  //                             style={{
  //                               color: THEME.sub,
  //                             }}
  //                           >
  //                             성격
  //                           </span>
  //                           <div className="space-y-1">
  //                             {c?.traits?.ocean &&
  //                             typeof c.traits.ocean === "object" ? (
  //                               Object.entries(c.traits.ocean).map(
  //                                 ([key, val]) => {
  //                                   const labelMap = {
  //                                     openness: "개방성",
  //                                     neuroticism: "신경성",
  //                                     extraversion: "외향성",
  //                                     agreeableness: "친화성",
  //                                     conscientiousness: "성실성",
  //                                   };
  //                                   const label = labelMap[key] ?? key;
  //                                   return (
  //                                     <div
  //                                       key={key}
  //                                       className="flex justify-between items-center"
  //                                     >
  //                                       <span
  //                                         className="text-[12px] opacity-70"
  //                                         style={{
  //                                           color: THEME.sub,
  //                                         }}
  //                                       >
  //                                         {label}
  //                                       </span>
  //                                       <span
  //                                         className="text-sm font-medium"
  //                                         style={{
  //                                           color: THEME.text,
  //                                         }}
  //                                       >
  //                                         {val}
  //                                       </span>
  //                                     </div>
  //                                   );
  //                                 },
  //                               )
  //                             ) : (
  //                               <div
  //                                 className="text-sm"
  //                                 style={{
  //                                   color: THEME.sub,
  //                                 }}
  //                               >
  //                                 성격 정보 없음
  //                               </div>
  //                             )}
  //                           </div>
  //                         </div>
  //                       </div>
  //                     </div>
  //                   </button>
  //                 ))}
  //               </div>
  //             )}

  //             {/* 시작 버튼: 초기 실행을 이미 했으면 숨김 */}
  //             {selectedScenario &&
  //               selectedCharacter &&
  //               simulationState === "IDLE" &&
  //               !pendingAgentDecision &&
  //               !showReportPrompt &&
  //               !hasInitialRun && (
  //                 <div className="flex justify-center">
  //                   <button
  //                     onClick={startSimulation}
  //                     disabled={startDisabled}
  //                     className={`px-8 py-3 rounded-lg font-semibold text-lg ${
  //                       startDisabled ? "opacity-60 cursor-not-allowed" : ""
  //                     }`}
  //                     style={{
  //                       backgroundColor: THEME.blurple,
  //                       color: THEME.white,
  //                       boxShadow: "0 10px 24px rgba(0,0,0,.35)",
  //                     }}
  //                   >
  //                     <Play className="inline mr-3" size={20} /> 시뮬레이션 시작
  //                   </button>
  //                 </div>
  //               )}
  //           </div>
  //         </div>

  //         <div
  //           className="px-6 py-4 flex items-center justify-between rounded-bl-3xl rounded-br-3xl"
  //           style={{
  //             backgroundColor: THEME.panel,
  //             borderTop: `1px solid ${THEME.border}`,
  //           }}
  //         >
  //           <div className="flex items-center gap-4">
  //             <Clock size={18} color={THEME.sub} />
  //             <span
  //               className="text-base font-medium"
  //               style={{ color: THEME.sub }}
  //             >
  //               진행률: {Math.round(progress)}%
  //             </span>
  //             <div
  //               className="w-48 h-3 rounded-full overflow-hidden"
  //               style={{ backgroundColor: THEME.panelDark }}
  //             >
  //               <div
  //                 className="h-3 rounded-full transition-all duration-300"
  //                 style={{
  //                   width: `${progress}%`,
  //                   backgroundColor: THEME.blurple,
  //                 }}
  //               />
  //             </div>
  //           </div>
  //           <div className="flex items-center gap-3">
  //             <span
  //               className="text-base font-medium"
  //               style={{ color: THEME.sub }}
  //             >
  //               상태: {simulationState}
  //             </span>
  //             {simulationState === "FINISH" && (
  //               <button
  //                 onClick={resetToSelection}
  //                 className="px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200"
  //                 style={{
  //                   backgroundColor: THEME.blurple,
  //                   color: THEME.white,
  //                   boxShadow: "0 6px 12px rgba(0,0,0,.25)",
  //                 }}
  //               >
  //                 다시 선택하기
  //               </button>
  //             )}
  //           </div>
  //         </div>
  //       </div>
  //     </div>

  //     {/* 완료 배너: pendingAgentDecision 동안 리포트 버튼 비활성 */}
  //     {sessionResult && progress >= 100 && (
  //       <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50">
  //         <div
  //           className="px-8 py-4 rounded-xl"
  //           style={{
  //             backgroundColor: THEME.panel,
  //             border: `1px solid ${THEME.border}`,
  //             boxShadow: "0 10px 24px rgba(0,0,0,.35)",
  //             color: THEME.text,
  //           }}
  //         >
  //           <div className="flex items-center gap-5">
  //             <div className="flex items-center gap-3">
  //               {sessionResult.isPhishing ? (
  //                 <AlertTriangle size={24} color={THEME.warn} />
  //               ) : (
  //                 <Check size={24} color={THEME.success} />
  //               )}
  //               <span
  //                 className="font-semibold text-lg"
  //                 style={{
  //                   color: sessionResult.isPhishing
  //                     ? THEME.warn
  //                     : THEME.success,
  //                 }}
  //               >
  //                 {sessionResult.isPhishing ? "피싱 감지" : "정상 대화"}
  //               </span>
  //             </div>
  //             <button
  //               onClick={() => setCurrentPage("report")}
  //               disabled={pendingAgentDecision}
  //               aria-disabled={pendingAgentDecision}
  //               title={
  //                 pendingAgentDecision
  //                   ? "에이전트 사용 여부 결정 후에 리포트를 보실 수 있습니다."
  //                   : "리포트 보기"
  //               }
  //               className={`px-6 py-2 rounded-md text-base font-medium transition-all duration-150`}
  //               style={{
  //                 backgroundColor: THEME.blurple,
  //                 color: THEME.white,
  //                 pointerEvents: pendingAgentDecision ? "none" : undefined,
  //                 opacity: pendingAgentDecision ? 0.5 : 1,
  //               }}
  //             >
  //               리포트 보기
  //             </button>
  //           </div>
  //         </div>
  //       </div>
  //     )}

  //     {/* 리포트 안내 모달 */}
  //     {showReportPrompt && (
  //       <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50 z-50">
  //         <div
  //           className="p-6 rounded-lg border"
  //           style={{
  //             borderColor: THEME.border,
  //             backgroundColor: THEME.panel,
  //           }}
  //         >
  //           <h3
  //             className="text-xl font-semibold mb-3"
  //             style={{ color: THEME.text }}
  //           >
  //             시뮬레이션이 완료되었습니다
  //           </h3>
  //           <p
  //             className="text-sm"
  //             style={{ color: THEME.sub, marginBottom: 16 }}
  //           >
  //             결과 리포트를 확인하시겠습니까?
  //           </p>
  //           <div className="flex justify-end gap-4">
  //             <button
  //               onClick={() => setShowReportPrompt(false)}
  //               className="px-4 py-2 rounded"
  //               style={{
  //                 backgroundColor: THEME.panelDark,
  //                 color: THEME.text,
  //               }}
  //             >
  //               닫기
  //             </button>
  //             <button
  //               onClick={() => setCurrentPage("report")}
  //               disabled={pendingAgentDecision}
  //               aria-disabled={pendingAgentDecision}
  //               title={
  //                 pendingAgentDecision
  //                   ? "에이전트 사용 여부 결정 후에 리포트를 보실 수 있습니다."
  //                   : "리포트 보기"
  //               }
  //               className={`px-4 py-2 rounded`}
  //               style={{
  //                 backgroundColor: THEME.blurple,
  //                 color: THEME.white,
  //                 pointerEvents: pendingAgentDecision ? "none" : undefined,
  //                 opacity: pendingAgentDecision ? 0.5 : 1,
  //               }}
  //             >
  //               리포트 보기
  //             </button>
  //           </div>
  //         </div>
  //       </div>
  //     )}
  //   </div>
  // );
//   return (
//   <div
//     className="min-h-screen"
//     style={{ backgroundColor: THEME.bg, color: THEME.text }}
//   >
//     <div className="container mx-auto px-6 py-12">
//       <div
//         className="w-full max-w-[1400px] mx-auto h-[calc(100vh-3rem)] rounded-3xl shadow-2xl border flex flex-col min-h-0"
//         style={{
//           borderColor: THEME.border,
//           backgroundColor: THEME.panel,
//         }}
//       >
//         {/* 상단 HUD */}
//         <HudBar COLORS={THEME} />

//         {/* 상단 상태/버튼 바 */}
//         <div
//           className="px-6 py-4 flex items-center justify-between"
//           style={{
//             backgroundColor: THEME.panel,
//             borderBottom: `1px dashed ${THEME.border}`,
//           }}
//         >
//           <div className="flex items-center gap-3">
//             <Badge
//               tone={selectedScenario ? "primary" : "neutral"}
//               COLORS={THEME}
//             >
//               {selectedScenario ? selectedScenario.name : "시나리오 미선택"}
//             </Badge>
//             <Badge
//               tone={selectedCharacter ? "success" : "neutral"}
//               COLORS={THEME}
//             >
//               {selectedCharacter ? selectedCharacter.name : "캐릭터 미선택"}
//             </Badge>
//           </div>

//           <div className="flex items-center gap-2">
//             {selectedScenario &&
//               simulationState === "IDLE" &&
//               !pendingAgentDecision && (
//                 <button
//                   onClick={() => {
//                     setSelectedScenario(null);
//                     setSelectedTag(null);
//                     addSystem("시나리오를 다시 선택하세요.");
//                   }}
//                   className="px-3 py-2 rounded-md text-sm font-medium border hover:opacity-90 transition"
//                   style={{
//                     backgroundColor: THEME.panelDark,
//                     borderColor: THEME.border,
//                     color: THEME.sub,
//                   }}
//                 >
//                   ← 시나리오 다시 선택
//                 </button>
//               )}

//             {selectedCharacter &&
//               simulationState === "IDLE" &&
//               !pendingAgentDecision && (
//                 <button
//                   onClick={() => {
//                     setSelectedCharacter(null);
//                     addSystem("캐릭터를 다시 선택하세요.");
//                   }}
//                   className="px-3 py-2 rounded-md text-sm font-medium border hover:opacity-90 transition"
//                   style={{
//                     backgroundColor: THEME.panelDark,
//                     borderColor: THEME.border,
//                     color: THEME.sub,
//                   }}
//                 >
//                   ← 캐릭터 다시 선택
//                 </button>
//               )}
//           </div>
//         </div>

//         {/* ===== 메인 영역: 좌(70%) / 우(30%) 분할 ===== */}
//         <div className="flex-1 min-h-0 flex" style={{ backgroundColor: THEME.bg }}>
//           {/* --- 왼쪽: 대화/선택 영역 (70%) --- */}
//           <div className="flex flex-col min-h-0" style={{ flex: "0 0 70%" }}>
//             <div className="px-6 py-6 flex-1 min-h-0">
//               <div
//                 ref={scrollContainerRef}
//                 className="h-full overflow-y-auto space-y-6"
//               >
//                 {!messages.some((m) => m.type === "chat") && (
//                   <SpinnerMessage
//                     simulationState={simulationState}
//                     COLORS={THEME}
//                   />
//                 )}

//                 {messages.map((m, index) => {
//                   const nm = normalizeMessage(m);
//                   const victimImg = selectedCharacter
//                     ? getVictimImage(selectedCharacter.photo_path)
//                     : null;
//                   return (
//                     <MessageBubble
//                       key={index}
//                       message={nm}
//                       selectedCharacter={selectedCharacter}
//                       victimImageUrl={victimImg}
//                       COLORS={THEME}
//                       label={nm.label}
//                       side={nm.side}
//                       role={nm.role}
//                     />
//                   );
//                 })}

//                 {/* 인라인 에이전트 결정 UI */}
//                 {pendingAgentDecision &&
//                   simulationState === "IDLE" &&
//                   !hasAgentRun && (
//                     <div className="flex justify-center mt-2">
//                       <div
//                         className="w-full max-w-[820px] p-4 rounded-md border"
//                         style={{
//                           backgroundColor: THEME.panel,
//                           borderColor: THEME.border,
//                         }}
//                       >
//                         <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
//                           <p className="text-sm" style={{ color: THEME.sub }}>
//                             에이전트를 사용하여 대화를 이어보시겠습니까?
//                             <span
//                               className="ml-2 text-xs"
//                               style={{ color: THEME.sub }}
//                             >
//                               (에이전트는 추가 분석/판단을 포함합니다)
//                             </span>
//                           </p>

//                           <div className="flex items-center gap-4 justify-end">
//                             <label
//                               className="inline-flex items-center gap-2 text-sm"
//                               style={{ color: THEME.sub }}
//                             >
//                               <input
//                                 type="checkbox"
//                                 style={{ accentColor: THEME.blurple }}
//                                 checked={!!agentVerbose}
//                                 onChange={(e) => setAgentVerbose(e.target.checked)}
//                               />
//                               상세근거(verbose)
//                             </label>

//                             <button
//                               onClick={declineAgentRun}
//                               className="px-4 py-2 rounded"
//                               style={{
//                                 backgroundColor: THEME.panelDark,
//                                 color: THEME.text,
//                               }}
//                             >
//                               아니요
//                             </button>

//                             <button
//                               onClick={startAgentRun}
//                               disabled={agentRunning || hasAgentRun}
//                               className="px-4 py-2 rounded text-white"
//                               style={{
//                                 backgroundColor: THEME.blurple,
//                                 opacity: agentRunning ? 0.5 : 1,
//                                 cursor: agentRunning ? "not-allowed" : undefined,
//                               }}
//                             >
//                               {agentRunning ? "로딩..." : "예"}
//                             </button>
//                           </div>
//                         </div>
//                       </div>
//                     </div>
//                   )}

//                 {/* 시나리오 선택 */}
//                 {needScenario && (
//                   <div className="flex justify-start">
//                     <SelectedCard
//                       title="시나리오 선택"
//                       subtitle="유형 칩을 먼저 눌러 필터링한 뒤, 상세 시나리오를 선택하세요."
//                       COLORS={THEME}
//                     >
//                       <div className="mb-4">
//                         {["기관 사칭형", "가족·지인 사칭", "대출사기형"].map((t) => (
//                           <Chip
//                             key={t}
//                             active={selectedTag === t}
//                             label={`${t}`}
//                             onClick={() =>
//                               setSelectedTag(selectedTag === t ? null : t)
//                             }
//                             COLORS={THEME}
//                           />
//                         ))}
//                       </div>

//                       <div
//                         className="flex-1 min-h-0 space-y-4 overflow-y-auto pr-1"
//                         style={{ maxHeight: "100%" }}
//                       >
//                         {filteredScenarios.map((s) => (
//                           <button
//                             key={s.id}
//                             onClick={() => setSelectedScenario(s)}
//                             className="w-full text-left rounded-lg p-4 hover:opacity-90"
//                             style={{
//                               backgroundColor: THEME.panelDark,
//                               border: `1px solid ${THEME.border}`,
//                               color: THEME.text,
//                             }}
//                           >
//                             <div className="flex items-center justify-between mb-2">
//                               <span className="font-semibold text-lg">{s.name}</span>
//                               <Badge tone="primary" COLORS={THEME}>
//                                 {s.type}
//                               </Badge>
//                             </div>
//                             <p
//                               className="text-base leading-relaxed"
//                               style={{ color: THEME.sub }}
//                             >
//                               {s.profile?.purpose ?? ""}
//                             </p>
//                           </button>
//                         ))}
//                       </div>
//                     </SelectedCard>
//                   </div>
//                 )}

//                 {/* 캐릭터 선택 */}
//                 {!needScenario && needCharacter && (
//                   <div
//                     className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 flex-1 min-h-0 overflow-y-auto pr-1"
//                     style={{ maxHeight: "100%" }}
//                   >
//                     <CustomCharacterCreate
//                       theme={THEME}
//                       onCreated={(createdVictim) => {
//                         setSelectedCharacter(createdVictim);
//                         addSystem(`커스텀 캐릭터 저장 및 선택: ${createdVictim.name}`);
//                       }}
//                     />

//                     {characters.map((c) => (
//                       <button key={c.id} onClick={() => setSelectedCharacter(c)}>
//                         <div
//                           className="flex flex-col h-full rounded-2xl overflow-hidden border hover:border-[rgba(168,134,42,.25)] transition-colors"
//                           style={{
//                             backgroundColor: THEME.panelDark,
//                             borderColor: THEME.border,
//                           }}
//                         >
//                           {getVictimImage(c.photo_path) ? (
//                             <div
//                               className="w-full h-44 bg-cover bg-center"
//                               style={{
//                                 backgroundImage: `url(${getVictimImage(c.photo_path)})`,
//                               }}
//                             />
//                           ) : (
//                             <div
//                               className="w-full h-44 flex items-center justify-center text-6xl"
//                               style={{ backgroundColor: THEME.panelDarker }}
//                             >
//                               {c.avatar ?? "👤"}
//                             </div>
//                           )}

//                           <div className="p-4 flex flex-col gap-3">
//                             <div className="flex items-center justify-between">
//                               <span
//                                 className="font-semibold text-lg"
//                                 style={{ color: THEME.text }}
//                               >
//                                 {c.name}
//                               </span>
//                               <span
//                                 className="text-xs px-2 py-1 rounded-md"
//                                 style={{
//                                   color: THEME.blurple,
//                                   backgroundColor: "rgba(168,134,42,.08)",
//                                   border: `1px solid rgba(168,134,42,.18)`,
//                                 }}
//                               >
//                                 프로필
//                               </span>
//                             </div>

//                             <div className="space-y-2 text-sm" style={{ color: THEME.sub }}>
//                               <div className="flex justify-between items-center">
//                                 <span className="text-[12px] opacity-70">나이</span>
//                                 <span className="font-medium" style={{ color: THEME.text }}>
//                                   {c.meta.age}
//                                 </span>
//                               </div>
//                               <div className="flex justify-between items-center">
//                                 <span className="text-[12px] opacity-70">성별</span>
//                                 <span className="font-medium" style={{ color: THEME.text }}>
//                                   {c.meta.gender}
//                                 </span>
//                               </div>
//                               <div className="flex justify-between items-center">
//                                 <span className="text-[12px] opacity-70">거주지</span>
//                                 <span className="font-medium truncate ml-2" style={{ color: THEME.text }}>
//                                   {c.meta.address}
//                                 </span>
//                               </div>
//                               <div className="flex justify-between items-center">
//                                 <span className="text-[12px] opacity-70">학력</span>
//                                 <span className="font-medium truncate ml-2" style={{ color: THEME.text }}>
//                                   {c.meta.education}
//                                 </span>
//                               </div>
//                             </div>

//                             <div>
//                               <span className="block text-[12px] opacity-70 mb-2" style={{ color: THEME.sub }}>
//                                 지식
//                               </span>
//                               <div className="space-y-1">
//                                 {Array.isArray(c?.knowledge?.comparative_notes) &&
//                                 c.knowledge.comparative_notes.length > 0 ? (
//                                   c.knowledge.comparative_notes.map((note, idx) => (
//                                     <div
//                                       key={idx}
//                                       className="text-sm font-medium leading-relaxed"
//                                       style={{ color: THEME.text }}
//                                     >
//                                       • {note}
//                                     </div>
//                                   ))
//                                 ) : (
//                                   <div className="text-sm" style={{ color: THEME.sub }}>
//                                     비고 없음
//                                   </div>
//                                 )}
//                               </div>
//                             </div>

//                             <div>
//                               <span className="block text-[12px] opacity-70 mb-2" style={{ color: THEME.sub }}>
//                                 성격
//                               </span>
//                               <div className="space-y-1">
//                                 {c?.traits?.ocean && typeof c.traits.ocean === "object" ? (
//                                   Object.entries(c.traits.ocean).map(([key, val]) => {
//                                     const labelMap = {
//                                       openness: "개방성",
//                                       neuroticism: "신경성",
//                                       extraversion: "외향성",
//                                       agreeableness: "친화성",
//                                       conscientiousness: "성실성",
//                                     };
//                                     const label = labelMap[key] ?? key;
//                                     return (
//                                       <div key={key} className="flex justify-between items-center">
//                                         <span className="text-[12px] opacity-70" style={{ color: THEME.sub }}>
//                                           {label}
//                                         </span>
//                                         <span className="text-sm font-medium" style={{ color: THEME.text }}>
//                                           {val}
//                                         </span>
//                                       </div>
//                                     );
//                                   })
//                                 ) : (
//                                   <div className="text-sm" style={{ color: THEME.sub }}>
//                                     성격 정보 없음
//                                   </div>
//                                 )}
//                               </div>
//                             </div>
//                           </div>
//                         </div>
//                       </button>
//                     ))}
//                   </div>
//                 )}

//                 {/* 시작 버튼 */}
//                 {selectedScenario &&
//                   selectedCharacter &&
//                   simulationState === "IDLE" &&
//                   !pendingAgentDecision &&
//                   !showReportPrompt &&
//                   !hasInitialRun && (
//                     <div className="flex justify-center">
//                       <button
//                         onClick={startSimulation}
//                         disabled={
//                           simulationState === "PREPARE" ||
//                           simulationState === "RUNNING" ||
//                           pendingAgentDecision ||
//                           hasInitialRun
//                         }
//                         className={`px-8 py-3 rounded-lg font-semibold text-lg ${
//                           simulationState === "PREPARE" ||
//                           simulationState === "RUNNING" ||
//                           pendingAgentDecision ||
//                           hasInitialRun
//                             ? "opacity-60 cursor-not-allowed"
//                             : ""
//                         }`}
//                         style={{
//                           backgroundColor: THEME.blurple,
//                           color: THEME.white,
//                           boxShadow: "0 10px 24px rgba(0,0,0,.35)",
//                         }}
//                       >
//                         <Play className="inline mr-3" size={20} /> 시뮬레이션 시작
//                       </button>
//                     </div>
//                   )}
//               </div>
//             </div>
//           </div>

//           {/* --- 오른쪽: 수사 보드 (30%) --- */}
//           <div
//             className="min-h-0 flex flex-col"
//             style={{
//               flex: "0 0 30%",
//               borderLeft: `1px solid ${THEME.border}`,
//               backgroundColor: THEME.panelDark,
//             }}
//           >
//             {/* InvestigationBoard 내부에서 자체 스크롤 처리 */}
//             <InvestigationBoard COLORS={THEME} insights={dummyInsights} />
//           </div>
//         </div>

//         {/* 하단 진행률 바 */}
//         <div
//           className="px-6 py-4 flex items-center justify-between rounded-bl-3xl rounded-br-3xl"
//           style={{
//             backgroundColor: THEME.panel,
//             borderTop: `1px solid ${THEME.border}`,
//           }}
//         >
//           <div className="flex items-center gap-4">
//             <Clock size={18} color={THEME.sub} />
//             <span className="text-base font-medium" style={{ color: THEME.sub }}>
//               진행률: {Math.round(progress)}%
//             </span>
//             <div
//               className="w-48 h-3 rounded-full overflow-hidden"
//               style={{ backgroundColor: THEME.panelDark }}
//             >
//               <div
//                 className="h-3 rounded-full transition-all duration-300"
//                 style={{
//                   width: `${progress}%`,
//                   backgroundColor: THEME.blurple,
//                 }}
//               />
//             </div>
//           </div>
//           <div className="flex items-center gap-3">
//             <span className="text-base font-medium" style={{ color: THEME.sub }}>
//               상태: {simulationState}
//             </span>
//             {simulationState === "FINISH" && (
//               <button
//                 onClick={resetToSelection}
//                 className="px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200"
//                 style={{
//                   backgroundColor: THEME.blurple,
//                   color: THEME.white,
//                   boxShadow: "0 6px 12px rgba(0,0,0,.25)",
//                 }}
//               >
//                 다시 선택하기
//               </button>
//             )}
//           </div>
//         </div>
//       </div>
//     </div>

//     {/* 완료 배너 */}
//     {sessionResult && progress >= 100 && (
//       <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50">
//         <div
//           className="px-8 py-4 rounded-xl"
//           style={{
//             backgroundColor: THEME.panel,
//             border: `1px solid ${THEME.border}`,
//             boxShadow: "0 10px 24px rgba(0,0,0,.35)",
//             color: THEME.text,
//           }}
//         >
//           <div className="flex items-center gap-5">
//             <div className="flex items-center gap-3">
//               {sessionResult.isPhishing ? (
//                 <AlertTriangle size={24} color={THEME.warn} />
//               ) : (
//                 <Check size={24} color={THEME.success} />
//               )}
//               <span
//                 className="font-semibold text-lg"
//                 style={{
//                   color: sessionResult.isPhishing ? THEME.warn : THEME.success,
//                 }}
//               >
//                 {sessionResult.isPhishing ? "피싱 감지" : "정상 대화"}
//               </span>
//             </div>
//             <button
//               onClick={() => setCurrentPage("report")}
//               disabled={pendingAgentDecision}
//               aria-disabled={pendingAgentDecision}
//               title={
//                 pendingAgentDecision
//                   ? "에이전트 사용 여부 결정 후에 리포트를 보실 수 있습니다."
//                   : "리포트 보기"
//               }
//               className="px-6 py-2 rounded-md text-base font-medium transition-all duration-150"
//               style={{
//                 backgroundColor: THEME.blurple,
//                 color: THEME.white,
//                 pointerEvents: pendingAgentDecision ? "none" : undefined,
//                 opacity: pendingAgentDecision ? 0.5 : 1,
//               }}
//             >
//               리포트 보기
//             </button>
//           </div>
//         </div>
//       </div>
//     )}

//     {/* 리포트 안내 모달 */}
//     {showReportPrompt && (
//       <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50 z-50">
//         <div
//           className="p-6 rounded-lg border"
//           style={{
//             borderColor: THEME.border,
//             backgroundColor: THEME.panel,
//           }}
//         >
//           <h3 className="text-xl font-semibold mb-3" style={{ color: THEME.text }}>
//             시뮬레이션이 완료되었습니다
//           </h3>
//           <p className="text-sm" style={{ color: THEME.sub, marginBottom: 16 }}>
//             결과 리포트를 확인하시겠습니까?
//           </p>
//           <div className="flex justify-end gap-4">
//             <button
//               onClick={() => setShowReportPrompt(false)}
//               className="px-4 py-2 rounded"
//               style={{ backgroundColor: THEME.panelDark, color: THEME.text }}
//             >
//               닫기
//             </button>
//             <button
//               onClick={() => setCurrentPage("report")}
//               disabled={pendingAgentDecision}
//               aria-disabled={pendingAgentDecision}
//               title={
//                 pendingAgentDecision
//                   ? "에이전트 사용 여부 결정 후에 리포트를 보실 수 있습니다."
//                   : "리포트 보기"
//               }
//               className="px-4 py-2 rounded"
//               style={{
//                 backgroundColor: THEME.blurple,
//                 color: THEME.white,
//                 pointerEvents: pendingAgentDecision ? "none" : undefined,
//                 opacity: pendingAgentDecision ? 0.5 : 1,
//               }}
//             >
//               리포트 보기
//             </button>
//           </div>
//         </div>
//       </div>
//     )}
//   </div>
// );

// };

// export default SimulatorPage;
  return (
    <div
      className="min-h-screen"
      style={{ backgroundColor: THEME.bg, color: THEME.text }}
    >
      <div className="container mx-auto px-6 py-12">
        <div
          className="w-full max-w-[1400px] mx-auto h-[calc(100vh-3rem)] rounded-3xl shadow-2xl border flex flex-col min-h-0"
          style={{
            borderColor: THEME.border,
            backgroundColor: THEME.panel,
          }}
        >
          {/* 상단 HUD */}
          <HudBar COLORS={THEME} />

          {/* 상단 상태/버튼 바 */}
          <div
            className="px-6 py-4 flex items-center justify-between"
            style={{
              backgroundColor: THEME.panel,
              borderBottom: `1px dashed ${THEME.border}`,
            }}
          >
            <div className="flex items-center gap-3">
              <Badge
                tone={selectedScenario ? "primary" : "neutral"}
                COLORS={THEME}
              >
                {selectedScenario ? selectedScenario.name : "시나리오 미선택"}
              </Badge>
              <Badge
                tone={selectedCharacter ? "success" : "neutral"}
                COLORS={THEME}
              >
                {selectedCharacter ? selectedCharacter.name : "캐릭터 미선택"}
              </Badge>
            </div>

            <div className="flex items-center gap-2">
            {/* 시나리오 다시 선택 */}
            {selectedScenario && showResetButtonsNow && (
              <button
                onClick={() => {
                  setSelectedScenario(null);
                  setSelectedTag(null);
                  addSystem("시나리오를 다시 선택하세요.");
                }}
                className="px-3 py-2 rounded-md text-sm font-medium border hover:opacity-90 transition"
                style={{
                  backgroundColor: THEME.panelDark,
                  borderColor: THEME.border,
                  color: THEME.sub,
                }}
              >
                ← 시나리오 다시 선택
              </button>
            )}

            {/* 캐릭터 다시 선택 */}
            {selectedCharacter && showResetButtonsNow && (
              <button
                onClick={() => {
                  setSelectedCharacter(null);
                  addSystem("캐릭터를 다시 선택하세요.");
                }}
                className="px-3 py-2 rounded-md text-sm font-medium border hover:opacity-90 transition"
                style={{
                  backgroundColor: THEME.panelDark,
                  borderColor: THEME.border,
                  color: THEME.sub,
                }}
              >
                ← 캐릭터 다시 선택
              </button>
            )}

            {/* ✅ 두 버튼이 활성화 되는 조건에서만 TTS 버튼도 같이 노출 */}
            {showTTSNow && (
              <button
                onClick={() => setOpen(true)}
                style={{
                  background: THEME.accent ?? THEME.border,
                  color: THEME.text,
                  padding: "6px 6px",
                  borderRadius: 8,
                  border: `1px solid ${THEME.border}`,
                  boxShadow: "0 6px 18px rgba(0,0,0,0.2)",
                  cursor: "pointer",
                  fontSize: "15px"
                }}
              >
                음성 대화 시뮬레이션
              </button>
            )}

            {/* 모달 컴포넌트는 그대로 두되, isOpen으로만 제어 */}
            <TTSModal isOpen={open} onClose={() => setOpen(false)} COLORS={THEME} />
          </div>
          </div>


          {/* ===== 메인 영역: 좌(대화/선택) / 우(수사보드) ===== */}
          <div className="flex-1 min-h-0 flex" style={{ backgroundColor: THEME.bg }}>
            {/* --- 왼쪽: 대화/선택 영역 --- */}
            <div
              className="flex flex-col min-h-0"
              style={{ flex: hasChatLog ? "0 0 70%" : "1 1 100%" }} // ✅ 대화로그 없으면 100%
            >
              <div className="px-6 py-6 flex-1 min-h-0">
                <div
                  ref={scrollContainerRef}
                  className="h-full overflow-y-auto space-y-6"
                >
                  {!messages.some((m) => m.type === "chat") && (
                    <SpinnerMessage
                      simulationState={simulationState}
                      COLORS={THEME}
                    />
                  )}

                  {messages.map((m, index) => {
                    const nm = normalizeMessage(m);
                    const victimImg = selectedCharacter
                      ? getVictimImage(selectedCharacter.photo_path)
                      : null;
                    return (
                      <MessageBubble
                        key={index}
                        message={nm}
                        selectedCharacter={selectedCharacter}
                        victimImageUrl={victimImg}
                        COLORS={THEME}
                        label={nm.label}
                        side={nm.side}
                        role={nm.role}
                      />
                    );
                  })}

                  {/* 인라인 에이전트 결정 UI */}
                  {pendingAgentDecision &&
                    simulationState === "IDLE" &&
                    !hasAgentRun && (
                      <div className="flex justify-center mt-2">
                        <div
                          className="w-full max-w-[820px] p-4 rounded-md border"
                          style={{
                            backgroundColor: THEME.panel,
                            borderColor: THEME.border,
                          }}
                        >
                          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                            <p className="text-sm" style={{ color: THEME.sub }}>
                              에이전트를 사용하여 대화를 이어보시겠습니까?
                              <span className="ml-2 text-xs" style={{ color: THEME.sub }}>
                                (에이전트는 추가 분석/판단을 포함합니다)
                              </span>
                            </p>

                            <div className="flex items-center gap-4 justify-end">
                              <label
                                className="inline-flex items-center gap-2 text-sm"
                                style={{ color: THEME.sub }}
                              >
                                <input
                                  type="checkbox"
                                  style={{ accentColor: THEME.blurple }}
                                  checked={!!agentVerbose}
                                  onChange={(e) => setAgentVerbose(e.target.checked)}
                                />
                                상세근거(verbose)
                              </label>

                              <button
                                onClick={declineAgentRun}
                                className="px-4 py-2 rounded"
                                style={{
                                  backgroundColor: THEME.panelDark,
                                  color: THEME.text,
                                }}
                              >
                                아니요
                              </button>

                              <button
                                onClick={startAgentRun}
                                disabled={agentRunning || hasAgentRun}
                                className="px-4 py-2 rounded text-white"
                                style={{
                                  backgroundColor: THEME.blurple,
                                  opacity: agentRunning ? 0.5 : 1,
                                  cursor: agentRunning ? "not-allowed" : undefined,
                                }}
                              >
                                {agentRunning ? "로딩..." : "예"}
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                  {/* 시나리오 선택 */}
                  {needScenario && (
                    <div className="flex justify-start">
                      <SelectedCard
                        title="시나리오 선택"
                        subtitle="유형 칩을 먼저 눌러 필터링한 뒤, 상세 시나리오를 선택하세요."
                        COLORS={THEME}
                      >
                        <div className="mb-4">
                          {["기관 사칭형", "가족·지인 사칭", "대출사기형"].map((t) => (
                            <Chip
                              key={t}
                              active={selectedTag === t}
                              label={`${t}`}
                              onClick={() =>
                                setSelectedTag(selectedTag === t ? null : t)
                              }
                              COLORS={THEME}
                            />
                          ))}
                        </div>

                       {/* ➕ 새 시나리오 추가 카드 */}
                        <div className="mb-4">
                          <CustomScenarioButton onClick={() => setShowCustomModal(true)} COLORS={THEME} />
                        </div>

                        <div
                          className="flex-1 min-h-0 space-y-4 overflow-y-auto pr-1"
                          style={{ maxHeight: "100%" }}
                        >
                          {combinedScenarios.map((s) => (
                            <button
                              key={s.id}
                              onClick={() => setSelectedScenario(s)}
                              className="w-full text-left rounded-lg p-4 hover:opacity-90"
                              style={{
                                backgroundColor: THEME.panelDark,
                                border: `1px solid ${THEME.border}`,
                                color: THEME.text,
                              }}
                            >
                              <div className="flex items-center justify-between mb-2">
                                <span className="font-semibold text-lg">{s.name}</span>
                                <Badge tone={s.type === "커스텀" ? "secondary" : "primary"} COLORS={THEME}>
                                  {s.type}
                                </Badge>
                              </div>
                              <p
                                className="text-base leading-relaxed"
                                style={{ color: THEME.sub }}
                              >
                                {s.profile?.purpose ?? ""}
                              </p>
                            </button>
                          ))}
                          {combinedScenarios.length === 0 && (
                            <div
                              className="w-full text-left rounded-lg p-4"
                              style={{
                                backgroundColor: THEME.panelDark,
                                border: `1px solid ${THEME.border}`,
                                color: THEME.sub,
                              }}
                            >
                              표시할 시나리오가 없습니다. “새 시나리오 추가”로 만들어 보세요.
                            </div>
                          )}
                        </div>
                      </SelectedCard>
                    </div>
                  )}

                  {/* 캐릭터 선택 */}
                  {!needScenario && needCharacter && (
                    <div
                      className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 flex-1 min-h-0 overflow-y-auto pr-1"
                      style={{ maxHeight: "100%" }}
                    >
                      <CustomCharacterCreate
                        theme={THEME}
                        onCreated={(createdVictim) => {
                          // 리스트 맨 끝에 추가
                          setCustomVictims((prev) => [...prev, createdVictim]);
                          // (옵션) 즉시 선택
                          setSelectedCharacter(createdVictim);
                          addSystem(`커스텀 캐릭터 저장 및 선택: ${createdVictim.name}`);
                        }}
                      />

                      {[...characters, ...customVictims].map((c) => (
                        <button key={c.id} onClick={() => setSelectedCharacter(c)}>
                          <div
                            className="flex flex-col h-full rounded-2xl overflow-hidden border hover:border-[rgba(168,134,42,.25)] transition-colors"
                            style={{
                              backgroundColor: THEME.panelDark,
                              borderColor: THEME.border,
                            }}
                          >
                            {getVictimImage(c.photo_path) ? (
                              <div
                                className="w-full h-44 bg-cover bg-center"
                                style={{
                                  backgroundImage: `url(${getVictimImage(c.photo_path)})`,
                                }}
                              />
                            ) : (
                              <div
                                className="w-full h-44 flex items-center justify-center text-6xl"
                                style={{ backgroundColor: THEME.panelDarker }}
                              >
                                {c.avatar ?? "👤"}
                              </div>
                            )}

                            <div className="p-4 flex flex-col gap-3">
                              <div className="flex items-center justify-between">
                                <span
                                  className="font-semibold text-lg"
                                  style={{ color: THEME.text }}
                                >
                                  {c.name}
                                </span>
                                <span
                                  className="text-xs px-2 py-1 rounded-md"
                                  style={{
                                    color: THEME.blurple,
                                    backgroundColor: "rgba(168,134,42,.08)",
                                    border: `1px solid rgba(168,134,42,.18)`,
                                  }}
                                >
                                  프로필
                                </span>
                              </div>

                              <div className="space-y-2 text-sm" style={{ color: THEME.sub }}>
                                <div className="flex justify-between items-center">
                                  <span className="text-[12px] opacity-70">나이</span>
                                  <span className="font-medium" style={{ color: THEME.text }}>
                                    {c.meta.age}
                                  </span>
                                </div>
                                <div className="flex justify-between items-center">
                                  <span className="text-[12px] opacity-70">성별</span>
                                  <span className="font-medium" style={{ color: THEME.text }}>
                                    {c.meta.gender}
                                  </span>
                                </div>
                                <div className="flex justify-between items-center">
                                  <span className="text-[12px] opacity-70">거주지</span>
                                  <span className="font-medium truncate ml-2" style={{ color: THEME.text }}>
                                    {c.meta.address}
                                  </span>
                                </div>
                                <div className="flex justify-between items-center">
                                  <span className="text-[12px] opacity-70">학력</span>
                                  <span className="font-medium truncate ml-2" style={{ color: THEME.text }}>
                                    {c.meta.education}
                                  </span>
                                </div>
                              </div>

                              <div>
                                <span className="block text-[12px] opacity-70 mb-2" style={{ color: THEME.sub }}>
                                  지식
                                </span>
                                <div className="space-y-1">
                                  {Array.isArray(c?.knowledge?.comparative_notes) &&
                                  c.knowledge.comparative_notes.length > 0 ? (
                                    c.knowledge.comparative_notes.map((note, idx) => (
                                      <div
                                        key={idx}
                                        className="text-sm font-medium leading-relaxed"
                                        style={{ color: THEME.text }}
                                      >
                                        • {note}
                                      </div>
                                    ))
                                  ) : (
                                    <div className="text-sm" style={{ color: THEME.sub }}>
                                      비고 없음
                                    </div>
                                  )}
                                </div>
                              </div>

                              <div>
                                <span className="block text-[12px] opacity-70 mb-2" style={{ color: THEME.sub }}>
                                  성격
                                </span>
                                <div className="space-y-1">
                                  {c?.traits?.ocean && typeof c.traits.ocean === "object" ? (
                                    Object.entries(c.traits.ocean).map(([key, val]) => {
                                      const labelMap = {
                                        openness: "개방성",
                                        neuroticism: "신경성",
                                        extraversion: "외향성",
                                        agreeableness: "친화성",
                                        conscientiousness: "성실성",
                                      };
                                      const label = labelMap[key] ?? key;
                                      return (
                                        <div key={key} className="flex justify-between items-center">
                                          <span className="text-[12px] opacity-70" style={{ color: THEME.sub }}>
                                            {label}
                                          </span>
                                          <span className="text-sm font-medium" style={{ color: THEME.text }}>
                                            {val}
                                          </span>
                                        </div>
                                      );
                                    })
                                  ) : (
                                    <div className="text-sm" style={{ color: THEME.sub }}>
                                      성격 정보 없음
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}

                  {/* 시작 버튼 */}
                  {selectedScenario &&
                    selectedCharacter &&
                    simulationState === "IDLE" &&
                    !pendingAgentDecision &&
                    !showReportPrompt &&
                    !hasInitialRun && (
                      <div className="flex justify-center">
                        <button
                          onClick={startSimulation}
                          disabled={
                            simulationState === "PREPARE" ||
                            simulationState === "RUNNING" ||
                            pendingAgentDecision ||
                            hasInitialRun
                          }
                          className={`px-8 py-3 rounded-lg font-semibold text-lg ${
                            simulationState === "PREPARE" ||
                            simulationState === "RUNNING" ||
                            pendingAgentDecision ||
                            hasInitialRun
                              ? "opacity-60 cursor-not-allowed"
                              : ""
                          }`}
                          style={{
                            backgroundColor: THEME.blurple,
                            color: THEME.white,
                            boxShadow: "0 10px 24px rgba(0,0,0,.35)",
                          }}
                        >
                          <Play className="inline mr-3" size={20} /> 시뮬레이션 시작
                        </button>
                      </div>
                    )}
                </div>
              </div>
            </div>

            {/* --- 오른쪽: 에이전트 패널(로그/분석 스위치) --- */}
{hasChatLog && (
  <div
    className="min-h-0 flex flex-col"
    style={{
      flex: "0 0 30%",
      borderLeft: `1px solid ${THEME.border}`,
      backgroundColor: THEME.panelDark,
      overflow: "hidden",
    }}
  >
    {/* 탭 바: 고정 높이 */}
    <div className="shrink-0 px-3 py-3" style={{ backgroundColor: THEME.panel }}>
      <div
        role="tablist"
        aria-label="에이전트 패널 전환"
        className="relative inline-flex items-center rounded-2xl border shadow-md overflow-hidden select-none"
        style={{
          borderColor: THEME.border,
          backgroundColor: THEME.panelDark,
        }}
      >
        {/* 하이라이트(선택된 탭 배경) - 수정된 transform 로직 */}
        <span
          aria-hidden="true"
          className="absolute inset-y-1 w-1/2 rounded-xl transition-transform duration-200 ease-out"
          style={{
            left: 6,
            backgroundColor: THEME.gold,
            transform:
              activeAgentTab === "insight" ? "translateX(0)" : "translateX(100%)",
            boxShadow: `0 6px 16px ${THEME.black}33`,
            zIndex: 0,
          }}
        />

        {/* 로그 탭 */}
        <button
          role="tab"
          aria-selected={activeAgentTab === "log"}   onClick={() => setActiveAgentTab("log")}
          className="relative z-10 flex items-center gap-2 px-6 py-2.5 text-sm font-semibold whitespace-nowrap focus:outline-none transition-colors duration-200"
          style={{
            color: activeAgentTab === "log" ? THEME.blurple : THEME.text, // THEME.sub 대신 THEME.text 사용
            background: "transparent",
          }}
        >
          <Terminal size={16} />
          <span>에이전트 로그</span>
        </button>

        {/* 분석 탭 */}
        <button
          role="tab"
          aria-selected={activeAgentTab === "insight"}
          onClick={() => setActiveAgentTab("insight")}
          className="relative z-10 flex items-center gap-2 px-6 py-2.5 text-sm font-semibold whitespace-nowrap focus:outline-none transition-colors duration-200"
          style={{
            color: activeAgentTab === "insight" ? THEME.blurple : THEME.text, // THEME.sub 대신 THEME.text 사용
            background: "transparent",
          }}
        >
          <Lightbulb size={16} />
          <span>에이전트 분석</span>
        </button>
      </div>
    </div>

    {/* 콘텐츠 영역: 유동 높이 + 내부 스크롤 */}
    <div className="flex-1 min-h-0 overflow-hidden" style={{ backgroundColor: THEME.bg }}>
      <div className="h-full overflow-auto">
        {activeAgentTab === "log" ? (
          <TerminalLog data={agentLogText} />
        ) : (
          <InvestigationBoard COLORS={THEME} insights={dummyInsights} />
        )}
      </div>
    </div>
  </div>
)}
            </div>


          {/* 하단 진행률 바 */}
          <div
            className="px-6 py-4 flex items-center justify-between rounded-bl-3xl rounded-br-3xl"
            style={{
              backgroundColor: THEME.panel,
              borderTop: `1px solid ${THEME.border}`,
            }}
          >
            <div className="flex items-center gap-4">
              <Clock size={18} color={THEME.sub} />
              <span className="text-base font-medium" style={{ color: THEME.sub }}>
                진행률: {Math.round(progress)}%
              </span>
              <div
                className="w-48 h-3 rounded-full overflow-hidden"
                style={{ backgroundColor: THEME.panelDark }}
              >
                <div
                  className="h-3 rounded-full transition-all duration-300"
                  style={{
                    width: `${progress}%`,
                    backgroundColor: THEME.blurple,
                  }}
                />
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-base font-medium" style={{ color: THEME.sub }}>
                상태: {simulationState}
              </span>
              {simulationState === "FINISH" && (
                <button
                  onClick={resetToSelection}
                  className="px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200"
                  style={{
                    backgroundColor: THEME.blurple,
                    color: THEME.white,
                    boxShadow: "0 6px 12px rgba(0,0,0,.25)",
                  }}
                >
                  다시 선택하기
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 완료 배너 */}
      {sessionResult && progress >= 100 && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50">
          <div
            className="px-8 py-4 rounded-xl"
            style={{
              backgroundColor: THEME.panel,
              border: `1px solid ${THEME.border}`,
              boxShadow: `0 10px 24px rgba(0,0,0,.35)`,
              color: THEME.text,
            }}
          >
          <div className="flex items-center gap-5">
            <button
              onClick={() => setCurrentPage("report")}
              disabled={pendingAgentDecision}
              aria-disabled={pendingAgentDecision}
              title={
                pendingAgentDecision
                  ? "에이전트 사용 여부 결정 후에 리포트를 보실 수 있습니다."
                  : "리포트 보기"
              }
              className="flex items-center gap-2 px-5 py-2 rounded-md text-base font-medium transition-all duration-150"
              style={{
                backgroundColor: THEME.blurple,
                color: THEME.white,
                pointerEvents: pendingAgentDecision ? "none" : undefined,
                opacity: pendingAgentDecision ? 0.5 : 1,
              }}
          >
            <FileBarChart2 size={22} />
            <span>리포트 보기</span>
          </button>
        </div>

          </div>
        </div>
      )}

      <CustomScenarioModal
        open={showCustomModal}
        onClose={handleCloseCustomModal}
        onSave={handleSaveCustomScenario}
        COLORS={THEME}
        selectedTag={selectedTag}
      />

      {/* 리포트 안내 모달 */}
      {showReportPrompt && (
        <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50 z-50">
          <div
            className="p-6 rounded-lg border"
            style={{
              borderColor: THEME.border,
              backgroundColor: THEME.panel,
            }}
          >
            <h3 className="text-xl font-semibold mb-3" style={{ color: THEME.text }}>
              시뮬레이션이 완료되었습니다
            </h3>
            <p className="text-sm" style={{ color: THEME.sub, marginBottom: 16 }}>
              결과 리포트를 확인하시겠습니까?
            </p>
            <div className="flex justify-end gap-4">
              <button
                onClick={() => setShowReportPrompt(false)}
                className="px-4 py-2 rounded"
                style={{ backgroundColor: THEME.panelDark, color: THEME.text }}
              >
                닫기
              </button>
              <button
                onClick={() => setCurrentPage("report")}
                disabled={pendingAgentDecision}
                aria-disabled={pendingAgentDecision}
                title={
                  pendingAgentDecision
                    ? "에이전트 사용 여부 결정 후에 리포트를 보실 수 있습니다."
                    : "리포트 보기"
                }
                className="px-4 py-2 rounded"
                style={{
                  backgroundColor: THEME.blurple,
                  color: THEME.white,
                  pointerEvents: pendingAgentDecision ? "none" : undefined,
                  opacity: pendingAgentDecision ? 0.5 : 1,
                }}
              >
                리포트 보기
              </button>
            </div>
          </div>
        </div>
      )}
      {/* 커스텀 시나리오 모달 */}
      <CustomScenarioModal
        open={showCustomModal}
        onClose={handleCloseCustomModal}
        onSave={handleSaveCustomScenario}
        COLORS={THEME}
        selectedTag={selectedTag}
      />
    </div>
  );
};
export default SimulatorPage;