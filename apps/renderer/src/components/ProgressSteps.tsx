import { Steps, Typography } from 'antd';

const { Text } = Typography;

interface ProgressStepsProps {
  currentStep: number; // 0-4: 未开始、解析中、匹配中、导出中、完成
  processingTime?: number; // 毫秒
}

export function ProgressSteps({ currentStep, processingTime }: ProgressStepsProps) {
  const steps = [
    { title: '解析 PDF', description: '正在解析银行流水' },
    { title: '智能匹配', description: '执行四阶段对账算法' },
    { title: '生成 Excel', description: '输出对账报告' },
    { title: '完成', description: '对账完成' },
  ];

  return (
    <div>
      <Steps
        current={currentStep}
        items={steps}
        status={currentStep === steps.length - 1 ? 'finish' : 'process'}
      />
      {processingTime && (
        <Text type="secondary" style={{ marginTop: '8px', display: 'block' }}>
          总耗时：{(processingTime / 1000).toFixed(2)} 秒
        </Text>
      )}
    </div>
  );
}
