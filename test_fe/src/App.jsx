import { useState } from 'react';
import { AlertCircle, Shield, BookOpen, Phone, CheckCircle, XCircle } from 'lucide-react';
import './App.css';

function App() {
  const [dialogues, setDialogues] = useState([]);
  const [detections, setDetections] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [guidelines, setGuidelines] = useState([]);
  const [preventions, setPreventions] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [error, setError] = useState(null);
  
  // 시나리오 설정
  const [scenarioType, setScenarioType] = useState('bank_impersonation');
  const [victimAge, setVictimAge] = useState(65);
  const [maxTurns, setMaxTurns] = useState(10);

  const startSimulation = async () => {
    // 초기화
    setDialogues([]);
    setDetections([]);
    setAnalysis(null);
    setGuidelines([]);
    setPreventions([]);
    setIsRunning(true);
    setIsComplete(false);
    setError(null);

    try {
      const response = await fetch('http://127.0.0.1:8000/api/simulate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          offender_id: 1,
          victim_id: 1,
          scenario_type: scenarioType,
          victim_age: victimAge,
          victim_tech_level: 'low',
          max_turns: maxTurns,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim()) continue;

          try {
            const { type, data } = JSON.parse(line);

            switch (type) {
              case 'start':
                console.log('Simulation started:', data);
                break;
              case 'dialogue':
                setDialogues(prev => [...prev, data]);
                break;
              case 'detection':
                if (data.is_suspicious) {
                  setDetections(prev => [...prev, data]);
                }
                break;
              case 'analysis':
                setAnalysis(data);
                break;
              case 'guideline':
                setGuidelines(prev => [...prev, data]);
                break;
              case 'prevention':
                setPreventions(prev => [...prev, data]);
                break;
              case 'complete':
                setIsComplete(true);
                setIsRunning(false);
                break;
              case 'error':
                console.error('Error:', data.message);
                setError(data.message);
                setIsRunning(false);
                break;
              default:
                console.log('Unknown event type:', type);
            }
          } catch (parseError) {
            console.error('Failed to parse line:', line, parseError);
          }
        }
      }
    } catch (error) {
      console.error('Stream error:', error);
      setError(error.message);
      setIsRunning(false);
    }
  };

  const getRiskColor = (level) => {
    switch (level) {
      case 'high': return 'text-red-600 bg-red-50';
      case 'medium': return 'text-orange-600 bg-orange-50';
      case 'low': return 'text-green-600 bg-green-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'high': return 'bg-red-100 text-red-800 border-red-300';
      case 'medium': return 'bg-orange-100 text-orange-800 border-orange-300';
      case 'low': return 'bg-blue-100 text-blue-800 border-blue-300';
      default: return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-6">
      <div className="max-w-7xl mx-auto">
        {/* 헤더 */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <Shield className="w-8 h-8 text-indigo-600" />
            <h1 className="text-3xl font-bold text-gray-800">보이스피싱 시뮬레이터</h1>
          </div>
          
          {/* 에러 메시지 */}
          {error && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
              <div className="flex items-center gap-2">
                <XCircle className="w-5 h-5 text-red-600" />
                <span className="text-red-800 font-semibold">오류 발생</span>
              </div>
              <p className="text-red-700 text-sm mt-1">{error}</p>
            </div>
          )}

          {/* 설정 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                시나리오 유형
              </label>
              <select
                value={scenarioType}
                onChange={(e) => setScenarioType(e.target.value)}
                disabled={isRunning}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-100"
              >
                <option value="bank_impersonation">은행원 사칭</option>
                <option value="government_officer">정부기관 사칭</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                피해자 나이: {victimAge}세
              </label>
              <input
                type="range"
                min="20"
                max="80"
                value={victimAge}
                onChange={(e) => setVictimAge(Number(e.target.value))}
                disabled={isRunning}
                className="w-full"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                최대 턴 수: {maxTurns}
              </label>
              <input
                type="range"
                min="5"
                max="20"
                value={maxTurns}
                onChange={(e) => setMaxTurns(Number(e.target.value))}
                disabled={isRunning}
                className="w-full"
              />
            </div>
          </div>

          <button
            onClick={startSimulation}
            disabled={isRunning}
            className={`w-full py-3 px-6 rounded-lg font-semibold text-white transition-colors ${
              isRunning
                ? 'bg-gray-400 cursor-not-allowed'
                : 'bg-indigo-600 hover:bg-indigo-700'
            }`}
          >
            {isRunning ? '시뮬레이션 진행 중...' : '시뮬레이션 시작'}
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 메인: 대화 */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow-lg p-6">
              <div className="flex items-center gap-2 mb-4">
                <Phone className="w-5 h-5 text-indigo-600" />
                <h2 className="text-xl font-bold text-gray-800">대화 시뮬레이션</h2>
              </div>
              
              <div className="space-y-3 max-h-[600px] overflow-y-auto">
                {dialogues.length === 0 && !isRunning && (
                  <p className="text-gray-500 text-center py-8">
                    시뮬레이션을 시작하면 대화가 표시됩니다
                  </p>
                )}
                
                {dialogues.map((dialogue, idx) => (
                  <div
                    key={idx}
                    className={`p-4 rounded-lg animate-fadeIn ${
                      dialogue.speaker === 'offender'
                        ? 'bg-red-50 border-l-4 border-red-500'
                        : 'bg-blue-50 border-l-4 border-blue-500'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-semibold text-sm">
                        {dialogue.speaker === 'offender' ? '🎭 공격자' : '👤 피해자'}
                      </span>
                      <span className="text-xs text-gray-500">턴 {dialogue.turn}</span>
                    </div>
                    <p className="text-gray-800">{dialogue.message}</p>
                  </div>
                ))}
                
                {isRunning && dialogues.length > 0 && (
                  <div className="text-center py-2">
                    <div className="inline-block animate-pulse text-indigo-600 text-2xl">●●●</div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* 사이드바 */}
          <div className="space-y-6">
            {/* 실시간 위험 감지 */}
            <div className="bg-white rounded-lg shadow-lg p-6">
              <div className="flex items-center gap-2 mb-4">
                <AlertCircle className="w-5 h-5 text-red-600" />
                <h3 className="text-lg font-bold text-gray-800">피싱 감지</h3>
              </div>
              
              {detections.length === 0 ? (
                <p className="text-sm text-gray-500">의심스러운 패턴이 감지되면 표시됩니다</p>
              ) : (
                <div className="space-y-3">
                  {detections.map((detection, idx) => (
                    <div key={idx} className="p-3 bg-red-50 border border-red-200 rounded-lg animate-fadeIn">
                      <div className="flex items-center gap-2 mb-1">
                        <XCircle className="w-4 h-4 text-red-600" />
                        <span className="text-sm font-semibold text-red-800">
                          위험도: {Math.round(detection.confidence * 100)}%
                        </span>
                      </div>
                      <p className="text-sm text-gray-700">{detection.message}</p>
                      {detection.patterns && detection.patterns.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {detection.patterns.map((pattern, i) => (
                            <span
                              key={i}
                              className="px-2 py-1 bg-red-100 text-red-700 text-xs rounded"
                            >
                              {pattern}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 분석 결과 */}
            {analysis && (
              <div className="bg-white rounded-lg shadow-lg p-6 animate-fadeIn">
                <h3 className="text-lg font-bold text-gray-800 mb-4">분석 결과</h3>
                
                <div className={`p-4 rounded-lg mb-4 ${getRiskColor(analysis.risk_level)}`}>
                  <div className="font-bold mb-2">
                    위험도: {analysis.risk_level.toUpperCase()}
                  </div>
                  <div className="text-sm">
                    점수: {(analysis.risk_score * 100).toFixed(0)}/100
                  </div>
                </div>
                
                <div className="space-y-3 text-sm">
                  <div>
                    <span className="font-semibold">공격자 전술:</span>
                    <ul className="mt-1 space-y-1">
                      {analysis.offender_tactics.map((tactic, i) => (
                        <li key={i} className="text-gray-700">• {tactic}</li>
                      ))}
                    </ul>
                  </div>
                  
                  <div>
                    <span className="font-semibold">피해자 취약점:</span>
                    <ul className="mt-1 space-y-1">
                      {analysis.victim_vulnerabilities.map((vuln, i) => (
                        <li key={i} className="text-gray-700">• {vuln}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            )}

            {/* 대응 지침 */}
            {guidelines.length > 0 && (
              <div className="bg-white rounded-lg shadow-lg p-6 animate-fadeIn">
                <div className="flex items-center gap-2 mb-4">
                  <BookOpen className="w-5 h-5 text-indigo-600" />
                  <h3 className="text-lg font-bold text-gray-800">대응 지침</h3>
                </div>
                
                <div className="space-y-3">
                  {guidelines.map((guide, idx) => (
                    <div
                      key={idx}
                      className={`p-3 border-2 rounded-lg animate-fadeIn ${getPriorityColor(guide.priority)}`}
                    >
                      <div className="font-semibold text-sm mb-1">{guide.category}</div>
                      <p className="text-sm">{guide.content}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 예방책 */}
            {preventions.length > 0 && (
              <div className="bg-white rounded-lg shadow-lg p-6 animate-fadeIn">
                <div className="flex items-center gap-2 mb-4">
                  <Shield className="w-5 h-5 text-green-600" />
                  <h3 className="text-lg font-bold text-gray-800">예방책</h3>
                </div>
                
                <div className="space-y-4">
                  {preventions.map((prevention, idx) => (
                    <div key={idx} className="border-l-4 border-green-500 pl-4 animate-fadeIn">
                      <div className="font-semibold text-sm text-gray-800 mb-1">
                        {prevention.title}
                      </div>
                      <p className="text-sm text-gray-600 mb-2">
                        {prevention.description}
                      </p>
                      <div className="flex items-start gap-2">
                        <CheckCircle className="w-4 h-4 text-green-600 mt-0.5 flex-shrink-0" />
                        <p className="text-sm text-green-700">
                          {prevention.actionable}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 완료 메시지 */}
        {isComplete && (
          <div className="mt-6 bg-green-50 border-2 border-green-500 rounded-lg p-6 text-center animate-fadeIn">
            <CheckCircle className="w-12 h-12 text-green-600 mx-auto mb-3" />
            <h3 className="text-xl font-bold text-green-800 mb-2">시뮬레이션 완료</h3>
            <p className="text-green-700">
              총 {dialogues.length}개의 대화 턴이 생성되었습니다
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;