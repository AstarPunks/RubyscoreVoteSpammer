import os, time, json, math
from decimal import Decimal
from dotenv import load_dotenv
from web3 import Web3

# === 設定 ===
CONTRACT_ADDRESS = "0xb0F3b3553cE518339c1B5807A392ae904fB658Ec"
CHAIN_ID = 1868                # Soneium mainnet（違うなら変更）
INTERVAL_SEC = 10              # 10秒ごと
VALUE_WEI = 0                  # vote()はpayable。ETHも送りたいならweiで指定
GAS_BUFFER = Decimal("1.20")   # estimateGasに2割マージン
TIP_FLOOR_WEI = 100            # tipの下限（必要に応じて調整）
PERCENTILE = 50                # priority feeのパーセンタイル(10/50/90あたり)

# 最小ABI（vote() と fallbackだけ）
ABI = [
  {"inputs": [], "name": "vote", "outputs": [], "stateMutability": "payable", "type": "function"},
  {"stateMutability": "payable", "type": "fallback"}
]

# === 準備 ===
load_dotenv()
RPC_URL = os.environ["RPC_URL"]
PRIVATE_KEY = os.environ["PRIVATE_KEY"]
w3 = Web3(Web3.HTTPProvider(RPC_URL))
acct = w3.eth.account.from_key(PRIVATE_KEY)
contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=ABI)

def build_fee_fields():
    """EIP-1559: baseFee + priority（fee_historyの分布を参照）"""
    latest = w3.eth.get_block("latest")
    base = latest.get("baseFeePerGas")
    if base is None:
        # 旧方式
        return {"gasPrice": w3.eth.gas_price}

    # 直近5ブロックのpriority分布
    hist = w3.eth.fee_history(5, "latest", [10, 50, 90])
    idx = {10:0, 50:1, 90:2}.get(PERCENTILE, 1)
    # hist["reward"] は各ブロックの [p10,p50,p90]
    suggested_tip = int(min(b[idx] for b in hist["reward"] if len(b) > idx))
    tip = max(TIP_FLOOR_WEI, suggested_tip)
    # baseに少しバッファ
    buffer = max(1, base // 20)  # +5%
    return {
        "maxPriorityFeePerGas": tip,
        "maxFeePerGas": base + tip + buffer
    }

def estimate_gas(tx_func, from_addr, value):
    # まずeth_callでrevertチェック
    data = tx_func._encode_transaction_data()
    try:
        w3.eth.call({"to": CONTRACT_ADDRESS, "from": from_addr, "value": value, "data": data}, "latest")
    except Exception as e:
        raise RuntimeError(f"eth_call reverted/failed: {e}")

    # 次にestimateGas
    return tx_func.estimate_gas({"from": from_addr, "value": value})

def send_once():
    tx_func = contract.functions.vote()
    # pendingを含むnonce（連投に強い）
    nonce = w3.eth.get_transaction_count(acct.address, "pending")
    fees = build_fee_fields()

    # ガス見積り
    gas_est = estimate_gas(tx_func, acct.address, VALUE_WEI)
    gas_limit = int(Decimal(gas_est) * GAS_BUFFER)

    # トランザクション作成
    base_tx = {
        "from": acct.address,
        "chainId": CHAIN_ID,
        "nonce": nonce,
        "value": VALUE_WEI,
        "gas": gas_limit,
        **fees
    }
    tx = tx_func.build_transaction(base_tx)

    # 署名 & 送信
    signed = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
    raw_tx = getattr(signed, "rawTransaction", None) or getattr(signed, "raw_transaction", None)

    try:
        tx_hash = w3.eth.send_raw_transaction(raw_tx)
        print(f"submitted: {tx_hash.hex()} (nonce={nonce}, gas={gas_limit})")
        return tx_hash
    except Exception as e:
        # underpriced/nonce mismatch 対策の簡易リトライ（tipを2倍にして再送）
        msg = str(e).lower()
        if "underpriced" in msg or "replacement" in msg or "fee too low" in msg:
            if "gasPrice" in tx:  # legacy分岐
                tx["gasPrice"] = int(tx["gasPrice"] * 2)
            else:
                tx["maxPriorityFeePerGas"] = int(tx["maxPriorityFeePerGas"] * 2)
                tx["maxFeePerGas"] = int(tx["maxFeePerGas"] * 2)
            signed2 = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
            raw2 = getattr(signed2, "rawTransaction", None) or getattr(signed2, "raw_transaction", None)
            tx_hash = w3.eth.send_raw_transaction(raw2)
            print(f"resubmitted with higher fee: {tx_hash.hex()}")
            return tx_hash
        raise

def main():
    print(f"From: {acct.address}")
    print(f"Contract: {CONTRACT_ADDRESS}")
    print(f"Interval: {INTERVAL_SEC}s, Value: {VALUE_WEI} wei")
    try:
        while True:
            try:
                txh = send_once()
                # すぐに掘られなくても次のnonceはpending基準で進む
            except Exception as e:
                print("send error:", e)
            time.sleep(INTERVAL_SEC)
    except KeyboardInterrupt:
        print("stopped.")

if __name__ == "__main__":
    main()
