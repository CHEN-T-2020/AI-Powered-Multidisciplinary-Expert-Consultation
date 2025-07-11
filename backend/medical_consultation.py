"""
Multi-agent medical consultation system using LangGraph
"""

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableLambda
from typing import TypedDict, List, Optional, Dict, Any
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
import os
import asyncio
import json
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 定义 Agent 类封装
class Agent:
    def __init__(self, instruction: str, role: str, model_info: str):
        self.role = role
        self.instruction = instruction
        self.model_info = model_info
        self.llm = ChatOpenAI(model=model_info, api_key=os.getenv('OPENAI_API_KEY'))
        self.history = []  
        
    def chat(self, message: str) -> str:
        try:
            if not self.history:
                self.history.append({"role": "system", "content": f"You are a {self.role}.\nInstructions: {self.instruction}"})
            self.history.append({"role": "user", "content": message})
            response = self.llm.invoke(self.history)
            self.history.append({"role": "assistant", "content": response.content})
            return response.content
        except Exception as e:
            logger.error(f"Error in {self.role} chat: {str(e)}")
            return f"Error: Unable to get response from {self.role}"

# 结构化专家模型
class ExpertAgent(BaseModel):
    role: str = Field(description="The expert's role or specialization.")
    description: str = Field(description="A brief description of their expertise.")
    hierarchy: Optional[str] = Field(description="Hierarchy relationship with others.")

class ExpertPlan(BaseModel):
    agents: List[ExpertAgent] = Field(description="List of recruited expert agents.")

# 工作流状态
class WorkflowState(TypedDict):
    question: str
    model: str
    agents_data: Optional[List[ExpertAgent]]
    agent_dict: Optional[dict]
    medical_agents: Optional[List]
    round_opinions: Optional[dict]
    final_answer: Optional[dict]
    decision: Optional[str]
    session_id: Optional[str]
    progress: Optional[float]
    current_step: Optional[str]
    start_time: Optional[datetime]
    end_time: Optional[datetime]

# Progress callback function
progress_callbacks = {}

def set_progress_callback(session_id: str, callback):
    """Set progress callback for a session"""
    progress_callbacks[session_id] = callback

def update_progress(session_id: str, progress: float, step: str):
    """Update progress for a session"""
    if session_id in progress_callbacks:
        try:
            progress_callbacks[session_id](progress, step)
        except Exception as e:
            logger.error(f"Error calling progress callback: {str(e)}")

# 1. 招募专家
def recruit_agents(state: WorkflowState):
    try:
        session_id = state.get("session_id")
        update_progress(session_id, 10.0, "正在组建AI专家团队...")
        
        llm = ChatOpenAI(model=state["model"], api_key=os.getenv('OPENAI_API_KEY'))
        structured_llm = llm.with_structured_output(ExpertPlan)
        system_instruction = (
            "You are an experienced medical expert who recruits a group of experts with diverse identities and asks them to discuss and solve the given medical query. "
            "Please respond in Chinese for role names and descriptions."
        )
        expert_count = 5
        recruitment_task_prompt = (
            f"Question: {state['question']}\n\n"
            f"You can recruit {expert_count} experts in different medical expertise. "
            "Considering the medical question, what kind of experts will you recruit to better make an accurate answer?\n"
            "Also, you need to specify the communication structure between experts (e.g., 呼吸科专家 == 儿科专家 == 心脏科专家 > 全科医生), or indicate if they are independent.\n\n"
            "For example, if you want to recruit five experts, your answer can be like:\n"
            "1. 儿科医生 - 专门从事婴幼儿、儿童和青少年的医疗保健工作 - Hierarchy: Independent\n"
            "2. 心脏科专家 - 专注于心脏和血管相关疾病的诊断和治疗 - Hierarchy: 儿科医生 > 心脏科专家\n"
            "3. 呼吸科专家 - 专门诊断和治疗呼吸系统疾病 - Hierarchy: Independent\n"
            "4. 新生儿科专家 - 专注于新生儿护理，特别是早产儿或有医疗问题的新生儿 - Hierarchy: Independent\n"
            "5. 医学遗传专家 - 专门研究基因和遗传疾病 - Hierarchy: Independent\n\n"
            "Please answer in above format, with Chinese role names and descriptions, and do not include your reason."
        )
        chat_messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": recruitment_task_prompt},
        ]
        
        plan = structured_llm.invoke(chat_messages)
        update_progress(session_id, 25.0, "专家团队组建完毕，正在初始化...")
        
        return {"agents_data": plan.agents}
    except Exception as e:
        logger.error(f"Error recruiting agents: {str(e)}")
        return {"agents_data": []}

# 2. 初始化专家对象
def init_agents(state: WorkflowState):
    try:
        session_id = state.get("session_id")
        update_progress(session_id, 30.0, "正在初始化专家...")
        
        agents = []
        agent_dict = {}
        for agent in state["agents_data"]:
            role = agent.role
            desc = agent.description
            agent_obj = Agent(f"You are a {role} who {desc}. Please respond in Chinese.", role, model_info=state['model'])
            agent_dict[role] = agent_obj
            agents.append(agent_obj)
        
        update_progress(session_id, 35.0, "专家初始化完成，开始收集意见...")
        return {"agent_dict": agent_dict, "medical_agents": agents}
    except Exception as e:
        logger.error(f"Error initializing agents: {str(e)}")
        return {"agent_dict": {}, "medical_agents": []}

# 3. 专家辩论与意见收集
def collect_opinions(state: WorkflowState):
    try:
        session_id = state.get("session_id")
        question = state['question']
        medical_agents = state['medical_agents']
        agent_dict = state['agent_dict']
        
        # Simplified debate process for faster execution
        num_rounds = 3  # Reduced from 5
        round_opinions = {str(n): {} for n in range(1, num_rounds+1)}
        
        # Round 1: Initial Opinions
        update_progress(session_id, 40.0, "专家们正在进行第一轮意见收集...")
        for role, agent in agent_dict.items():
            try:
                opinion = agent.chat(f'根据医疗问题，请给出您的专业意见和初步诊断。\n\n问题: {question}\n\n请用中文回答，格式如下：\n\n诊断意见：')
                round_opinions["1"][role] = opinion
            except Exception as e:
                logger.error(f"Error getting opinion from {role}: {str(e)}")
                round_opinions["1"][role] = f"专家 {role} 暂时无法提供意见"
        
        # Round 2: Discussion
        update_progress(session_id, 60.0, "专家们正在进行第二轮讨论...")
        if len(round_opinions["1"]) > 0:
            assessment = "\n".join(f"{k}: {v}" for k, v in round_opinions["1"].items())
            for role, agent in agent_dict.items():
                try:
                    opinion = agent.chat(f'请基于其他专家的意见，提供您的进一步分析和建议。\n\n其他专家意见：\n{assessment}\n\n请用中文回答：')
                    round_opinions["2"][role] = opinion
                except Exception as e:
                    logger.error(f"Error in round 2 for {role}: {str(e)}")
                    round_opinions["2"][role] = f"专家 {role} 在第二轮讨论中无法提供意见"
        
        # Round 3: Final discussion
        update_progress(session_id, 70.0, "专家们正在进行最终讨论...")
        if len(round_opinions["2"]) > 0:
            assessment = "\n".join(f"{k}: {v}" for k, v in round_opinions["2"].items())
            for role, agent in agent_dict.items():
                try:
                    opinion = agent.chat(f'基于前两轮讨论，请提供您的最终分析意见。\n\n讨论总结：\n{assessment}\n\n请用中文回答：')
                    round_opinions["3"][role] = opinion
                except Exception as e:
                    logger.error(f"Error in round 3 for {role}: {str(e)}")
                    round_opinions["3"][role] = f"专家 {role} 在最终讨论中无法提供意见"
        
        return {"round_opinions": round_opinions}
    except Exception as e:
        logger.error(f"Error collecting opinions: {str(e)}")
        return {"round_opinions": {}}

# 4. 汇总每个专家的最终决策
def finalize_per_agent(state: WorkflowState):
    try:
        session_id = state.get("session_id")
        update_progress(session_id, 80.0, "正在汇总各专家最终意见...")
        
        final_answers = {}
        for agent in state['medical_agents']:
            try:
                response = agent.chat(f"现在您已经与其他医疗专家进行了讨论，请结合您的专业知识和其他专家的意见，对以下问题给出最终答案：\n{state['question']}\n\n请用中文回答，包含诊断和建议：")
                final_answers[agent.role] = response
            except Exception as e:
                logger.error(f"Error getting final answer from {agent.role}: {str(e)}")
                final_answers[agent.role] = f"专家 {agent.role} 无法提供最终意见"
        
        return {"final_answer": final_answers}
    except Exception as e:
        logger.error(f"Error finalizing per agent: {str(e)}")
        return {"final_answer": {}}

# 5. 主持人最终决策
def finalize_decision(state: WorkflowState):
    try:
        session_id = state.get("session_id")
        update_progress(session_id, 90.0, "正在生成最终会诊结论...")
        
        summary = "\n".join(f"{k}: {v}" for k, v in state['final_answer'].items())
        mod = Agent("You are a final medical decision maker who reviews all opinions from different medical experts and makes final decision. Please respond in Chinese.", "主持人", model_info=state['model'])
        
        decision = mod.chat(f"根据各位专家的最终意见，请综合分析并给出最终的医疗会诊结论。您的答案应该包含诊断结论、诊断依据、建议检查、治疗建议和注意事项。\n\n各专家意见：\n{summary}\n\n问题：{state['question']}\n\n请用中文给出详细的最终结论：")
        
        update_progress(session_id, 100.0, "会诊完成！")
        return {"decision": decision, "end_time": datetime.now()}
    except Exception as e:
        logger.error(f"Error finalizing decision: {str(e)}")
        return {"decision": "由于系统问题，无法生成最终结论", "end_time": datetime.now()}

# 构建医疗会诊 LangGraph 流程
def create_medical_consultation_graph():
    medical_graph = StateGraph(WorkflowState)
    medical_graph.add_node("recruit", RunnableLambda(recruit_agents))
    medical_graph.add_node("init_agents", RunnableLambda(init_agents))
    medical_graph.add_node("collect_opinions", RunnableLambda(collect_opinions))
    medical_graph.add_node("finalize_per_agent", RunnableLambda(finalize_per_agent))
    medical_graph.add_node("finalize", RunnableLambda(finalize_decision))
    medical_graph.set_entry_point("recruit")
    medical_graph.add_edge("recruit", "init_agents")
    medical_graph.add_edge("init_agents", "collect_opinions")
    medical_graph.add_edge("collect_opinions", "finalize_per_agent")
    medical_graph.add_edge("finalize_per_agent", "finalize")
    medical_graph.set_finish_point("finalize")
    
    return medical_graph.compile()

# 异步执行医疗会诊
async def run_medical_consultation(question: str, model: str = "gpt-4o-mini", session_id: str = None):
    """
    Run medical consultation workflow
    """
    try:
        graph = create_medical_consultation_graph()
        
        initial_state = {
            "question": question,
            "model": model,
            "session_id": session_id,
            "start_time": datetime.now(),
            "progress": 0.0,
            "current_step": "开始会诊..."
        }
        
        # Execute the graph
        result = await graph.ainvoke(initial_state)
        
        # Calculate duration
        if result.get("start_time") and result.get("end_time"):
            duration = (result["end_time"] - result["start_time"]).total_seconds()
        else:
            duration = 0
        
        # Format response
        response = {
            "session_id": session_id,
            "question": question,
            "experts": [{"role": agent.role, "description": agent.description, "hierarchy": agent.hierarchy} 
                       for agent in result.get("agents_data", [])],
            "round_opinions": result.get("round_opinions", {}),
            "final_answers": result.get("final_answer", {}),
            "decision": result.get("decision", "无法生成结论"),
            "duration": duration,
            "start_time": result.get("start_time").isoformat() if result.get("start_time") else None,
            "end_time": result.get("end_time").isoformat() if result.get("end_time") else None
        }
        
        return response
        
    except Exception as e:
        logger.error(f"Error in medical consultation: {str(e)}")
        return {
            "session_id": session_id,
            "question": question,
            "experts": [],
            "round_opinions": {},
            "final_answers": {},
            "decision": f"系统错误：{str(e)}",
            "duration": 0,
            "start_time": None,
            "end_time": None
        }

# 清理会话回调
def cleanup_session(session_id: str):
    """Clean up session data"""
    if session_id in progress_callbacks:
        del progress_callbacks[session_id]