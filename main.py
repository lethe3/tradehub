"""
TradeHub 入口文件
只做组装和调度，不写具体业务逻辑
"""
from feishu import FeishuBot, BitableClient
from ai import OCRService, LLMService


class TradeHub:
    """TradeHub 主类，负责组装各层模块"""

    def __init__(self, config: dict):
        self.bot = FeishuBot(config.get('feishu'))
        self.bitable = BitableClient(config.get('bitable'))
        self.ocr = OCRService(config.get('ocr'))
        self.llm = LLMService(config.get('llm'))

    def run(self):
        """启动服务"""
        self.bot.start()


if __name__ == '__main__':
    # TODO: 加载配置
    config = {}
    app = TradeHub(config)
    app.run()
