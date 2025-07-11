import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { Separator } from './ui/separator';
import { Progress } from './ui/progress';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from './ui/accordion';
import { Clock, Users, MessageSquare, CheckCircle, AlertCircle, XCircle } from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const MedicalConsultation = () => {
  const [question, setQuestion] = useState('');
  const [isConsulting, setIsConsulting] = useState(false);
  const [consultationResult, setConsultationResult] = useState(null);
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState('');
  const [sessionId, setSessionId] = useState(null);
  const [error, setError] = useState(null);
  const eventSourceRef = useRef(null);

  const exampleQuestions = [
    "3岁男孩反复咳嗽2个月，夜间加重，运动后气促，既往有湿疹史，请问可能的诊断是什么？",
    "新生儿出生后出现呼吸困难，心率过快，皮肤发绀，胸片显示心脏增大，请评估可能的心脏疾病类型？",
    "8岁女孩身高明显低于同龄人，骨龄延迟，甲状腺功能检查异常，请分析可能的内分泌疾病？"
  ];

  const startConsultation = async () => {
    if (!question.trim()) return;
    
    try {
      setIsConsulting(true);
      setError(null);
      setProgress(0);
      setCurrentStep('正在启动会诊...');
      setConsultationResult(null);

      // Start consultation
      const response = await axios.post(`${API}/consultation/start`, {
        question: question.trim(),
        model: "gpt-4o-mini"
      });

      const newSessionId = response.data.session_id;
      setSessionId(newSessionId);

      // Start listening to progress updates
      startProgressStream(newSessionId);

    } catch (err) {
      console.error('Error starting consultation:', err);
      setError('启动会诊失败: ' + (err.response?.data?.error || err.message));
      setIsConsulting(false);
    }
  };

  const startProgressStream = (sessionId) => {
    // Close existing connection if any
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    // Create new EventSource for progress updates
    const progressInterval = setInterval(async () => {
      try {
        const response = await axios.get(`${API}/consultation/${sessionId}/progress`);
        const data = response.data;
        
        setProgress(data.progress || 0);
        setCurrentStep(data.current_step || '');
        
        if (data.status === 'completed' && data.result) {
          setConsultationResult(data.result);
          setIsConsulting(false);
          clearInterval(progressInterval);
        } else if (data.status === 'error') {
          setError(data.result?.error || '会诊过程中发生错误');
          setIsConsulting(false);
          clearInterval(progressInterval);
        }
      } catch (err) {
        console.error('Error getting progress:', err);
        setError('获取进度失败: ' + (err.response?.data?.error || err.message));
        setIsConsulting(false);
        clearInterval(progressInterval);
      }
    }, 2000); // Poll every 2 seconds

    // Store interval reference for cleanup
    eventSourceRef.current = { close: () => clearInterval(progressInterval) };
  };

  const handleSubmit = () => {
    startConsultation();
  };

  const handleExampleClick = (exampleQuestion) => {
    setQuestion(exampleQuestion);
  };

  const handleReset = () => {
    setQuestion('');
    setConsultationResult(null);
    setProgress(0);
    setCurrentStep('');
    setError(null);
    setSessionId(null);
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}分${secs}秒`;
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-8">
      {/* 标题区域 */}
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
          多智能体医疗会诊系统
        </h1>
        <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
          专业的AI医疗专家团队为您提供全面、可信赖的医疗咨询服务
        </p>
      </div>

      {/* 错误提示 */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-red-600">
              <XCircle className="h-5 w-5" />
              <p>{error}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 问题输入模块 */}
      {!isConsulting && !consultationResult && (
        <Card className="shadow-lg border-0 bg-gradient-to-br from-white to-blue-50">
          <CardHeader>
            <CardTitle className="text-2xl flex items-center gap-2">
              <MessageSquare className="text-blue-600" />
              请详细描述您的医疗问题
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <Textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="请在此详细描述您的医疗问题，包括症状、病史、检查结果等信息。系统将为您组建AI专家团队进行专业会诊。"
              className="min-h-[120px] text-base resize-none border-2 focus:border-blue-500 transition-all duration-200"
            />
            
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">快速体验示例问题：</p>
              <div className="flex flex-wrap gap-2">
                {exampleQuestions.map((example, index) => (
                  <Button
                    key={index}
                    variant="outline"
                    size="sm"
                    onClick={() => handleExampleClick(example)}
                    className="text-left h-auto p-3 hover:bg-blue-50 transition-colors"
                  >
                    示例 {index + 1}
                  </Button>
                ))}
              </div>
            </div>

            <Button 
              onClick={handleSubmit}
              disabled={!question.trim()}
              className="w-full py-6 text-lg font-semibold bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 transition-all duration-200 shadow-lg"
            >
              <Users className="mr-2" />
              开始会诊
            </Button>
          </CardContent>
        </Card>
      )}

      {/* 过程反馈模块 */}
      {isConsulting && (
        <Card className="shadow-lg border-0 bg-gradient-to-br from-blue-50 to-purple-50">
          <CardHeader>
            <CardTitle className="text-2xl flex items-center gap-2">
              <AlertCircle className="text-blue-600 animate-pulse" />
              会诊进行中...
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-lg font-medium">{currentStep}</p>
                <Badge variant="outline" className="text-blue-600">
                  {Math.round(progress)}%
                </Badge>
              </div>
              <Progress value={progress} className="h-3" />
            </div>
            
            <div className="bg-white rounded-lg p-4 border-l-4 border-blue-500">
              <p className="text-sm text-muted-foreground">
                您的问题：{question}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 结果展示模块 */}
      {consultationResult && (
        <div className="space-y-6">
          {/* 最终结论卡片 */}
          <Card className="shadow-xl border-0 bg-gradient-to-br from-green-50 to-emerald-50">
            <CardHeader>
              <CardTitle className="text-2xl flex items-center gap-2">
                <CheckCircle className="text-green-600" />
                最终会诊结论
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-white rounded-lg p-6 border-l-4 border-green-500">
                <h3 className="font-semibold text-lg mb-3">诊断结论：</h3>
                <p className="text-base leading-relaxed whitespace-pre-line">
                  {consultationResult.decision}
                </p>
              </div>
              
              <div className="flex items-center justify-between text-sm text-muted-foreground bg-white rounded-lg p-4">
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  <span>总耗时：{formatTime(consultationResult.duration || 0)}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  <span>参与专家：{consultationResult.experts?.length || 0}位</span>
                </div>
              </div>
              
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-sm font-medium mb-2">您的问题：</p>
                <p className="text-sm text-muted-foreground">{consultationResult.question}</p>
              </div>
            </CardContent>
          </Card>

          {/* 专家团队卡片 */}
          {consultationResult.experts && consultationResult.experts.length > 0 && (
            <Card className="shadow-lg">
              <CardHeader>
                <CardTitle className="text-xl flex items-center gap-2">
                  <Users className="text-blue-600" />
                  本次会诊专家团队
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {consultationResult.experts.map((expert, index) => (
                    <div key={index} className="bg-gradient-to-br from-blue-50 to-purple-50 rounded-lg p-4 border border-blue-200">
                      <div className="flex items-start gap-3">
                        <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center text-white font-bold text-sm">
                          {index + 1}
                        </div>
                        <div className="flex-1">
                          <h4 className="font-semibold text-base">{expert.role}</h4>
                          <p className="text-sm text-muted-foreground mt-1">{expert.description}</p>
                          {expert.hierarchy && (
                            <Badge variant="outline" className="mt-2 text-xs">
                              {expert.hierarchy}
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* 各专家最终意见卡片 */}
          {consultationResult.final_answers && Object.keys(consultationResult.final_answers).length > 0 && (
            <Card className="shadow-lg">
              <CardHeader>
                <CardTitle className="text-xl">各专家独立意见</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {Object.entries(consultationResult.final_answers).map(([role, opinion], index) => (
                    <div key={index} className="border rounded-lg p-4 hover:bg-gray-50 transition-colors">
                      <div className="flex items-start gap-3">
                        <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-500 rounded-full flex items-center justify-center text-white font-medium text-sm">
                          {index + 1}
                        </div>
                        <div className="flex-1">
                          <h4 className="font-semibold text-base text-blue-600 mb-2">{role}：</h4>
                          <p className="text-sm text-gray-700 leading-relaxed">{opinion}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* 完整会诊记录 */}
          {consultationResult.round_opinions && Object.keys(consultationResult.round_opinions).length > 0 && (
            <Card className="shadow-lg">
              <CardHeader>
                <CardTitle className="text-xl">完整会诊记录（面向研究人员）</CardTitle>
              </CardHeader>
              <CardContent>
                <Accordion type="single" collapsible className="w-full">
                  <AccordionItem value="detailed-records">
                    <AccordionTrigger className="text-left">
                      <div className="flex items-center gap-2">
                        <MessageSquare className="h-4 w-4" />
                        查看多轮讨论详细记录
                      </div>
                    </AccordionTrigger>
                    <AccordionContent>
                      <div className="space-y-6 mt-4">
                        {Object.entries(consultationResult.round_opinions).map(([round, opinions]) => (
                          <div key={round} className="border rounded-lg p-4 bg-gray-50">
                            <h4 className="font-semibold mb-3 text-blue-600">第{round}轮讨论</h4>
                            <div className="space-y-3">
                              {Object.entries(opinions).map(([expert, opinion]) => (
                                <div key={expert} className="bg-white rounded p-3 border-l-4 border-blue-200">
                                  <p className="font-medium text-sm text-blue-600 mb-1">{expert}：</p>
                                  <p className="text-xs text-gray-600">{opinion}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
              </CardContent>
            </Card>
          )}

          {/* 重新开始按钮 */}
          <div className="flex justify-center">
            <Button 
              onClick={handleReset}
              variant="outline"
              className="px-8 py-3 text-base hover:bg-blue-50 border-blue-200"
            >
              开始新的会诊
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default MedicalConsultation;