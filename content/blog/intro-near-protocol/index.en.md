---
title: "NEAR Protocol: Architecture, Token Economics, and Risks"
date: 2026-10-17
description: "An introduction to NEAR’s sharded architecture, token economics, value accrual, governance, and security risks."
authors: [donny]
images: [thumbnail.webp]
categories: [Blockchain]
tags: [NEAR, Blockchain, Proof of Stake, Tokenomics]
---

> Research cutoff: October 15, 2026. Market figures and protocol-status descriptions reflect the dates cited below.

## 1. Project Overview and the Problem It Addresses

NEAR is a general-purpose proof-of-stake layer-1 blockchain whose native token is NEAR. The two co-founders, Illia Polosukhin and Alexander Skidanov, both came out of AI research. They were frustrated by the fact that payments using the existing blockchain infrastructure were unusable, so they decided to build a scalable blockchain. [^1] Mainnet was launched in 2020, and the ecosystem now involves the NEAR Foundation, Near One, independent validators, and a growing developer community. [^2] From the history of NEAR Protocol, it is interesting to see that it started with a straightforward goal — cheap, fast smart-contract execution — and has since broadened its narrative toward chain abstraction and “User-Owned AI”.

The two main problems NEAR is designed to solve are usability and scalability. [^1] The first one refers to the fact that traditional blockchains like Bitcoin and Ethereum can be difficult for everyday users because they need to manage wallets, private keys, and transaction processes that most users find frustrating. They also face scalability issues since their throughput is capped at a few dozen transactions per second by design. As a result, they cannot handle high demand without congestion and high fees.

NEAR addresses these problems in two ways. Nightshade divides the work of processing transactions across groups called shards, allowing different portions of the network to work in parallel. NEAR also supports human-readable account names and multiple permissioned keys for one account. [^3] [^4] More recently, NEAR Intents and Chain Signatures have been introduced to make transactions across different blockchains much easier to use. [^5] [^6]

## 2. Technical Architecture

| Layer | Main components | Role |
| --- | --- | --- |
| Protocol | nearcore, accounts, access keys, signatures | Defines accounts, permissions, and basic protocol operations. |
| Consensus | Thresholded Proof of Stake, stake-weighted approvals | Selects producers and establishes block finality. |
| Data | Nightshade, shards, chunks, state witnesses | Distributes state and transaction processing across shards. |
| Logic | WebAssembly runtime, asynchronous receipts, callbacks | Executes contracts and handles cross-contract interactions. |
| Application | Wallets, dApps, NEAR Intents, Chain Signatures | Connects users to on-chain and cross-chain services. |

### Protocol Layer

NEAR’s protocol layer is built around nearcore, a Rust-based reference client that handles peer-to-peer networking, cryptographic signatures, and hashed state commitments. [^7] One distinctive feature of NEAR’s account system is that it gives users more control over their tokens and smart contracts than others. To be more specific, NEAR uses an account-based model rather than Bitcoin’s unspent-transaction-output (UTXO) model, and supports multiple keys per account and restricted function-call permissions out of the box.

A named account can have more than one access key. A full-access key can authorize broad account actions, while a function-call key can be restricted to specific contracts, particular contract methods, and a particular gas allowance. An application can therefore request limited permission (similar to a fine-grained access token in software development) without necessarily receiving the ability to transfer all the user’s funds. This limits the potential damage if the corresponding private key is compromised, although an attacker could still execute permitted contract functions and consume the authorized gas budget. [^3] [^4]

For ordinary transaction signatures, the network supports Ed25519 and secp256k1. A 2026 protocol upgrade (July 20, 2026) also introduced ML-DSA-65, a post-quantum signature option for account access keys and transactions. [^8] It is an option rather than an automatic migration of all users.

More importantly, this upgrade did not change validator signing keys, consensus signatures, or the security assumptions of external bridges. Therefore, it should be described as progress toward quantum-resistant account security, not as proof that all of NEAR is quantum-safe. [^9]

### Consensus Layer

NEAR secures consensus with a specific form of PoS called Thresholded Proof of Stake (TPoS). Validators commit NEAR as stake and may receive delegated stake from other holders. During each epoch, an auction sets a market-determined minimum stake per seat, so validators earn seats in proportion to their stake. Selected validators then produce blocks and shard chunks in a stake-weighted way. [^10] The consensus rules require approvals from more than two-thirds of the relevant producing stake, with finality reached after two consecutive successor blocks. [^11] The commonly cited 600-millisecond block time and approximately 1.2-second finality describe the network’s intended or reported performance. [^12] If more than one-third of participating stake becomes unavailable or fails to approve blocks, finalization will be interrupted, creating a liveness concern. [^11]

### Data Layer

NEAR uses Nightshade, an open-source sharding mechanism for scalability. Instead of requiring every node to process every transaction, NEAR divides accounts and their associated states across multiple shards, allowing transactions to be processed in parallel. A shard processes its own transactions and produces a chunk. The block producer then organizes a bunch of chunks to form a block. NEAR initially launched with one shard in 2020 and expanded to nine mainnet shards after its 2025 update. [^13]

A simple way to understand Nightshade is to consider two unrelated transfers assigned to different shards. They can then be processed in parallel rather than executed in series on a single shard. When a smart contract on shard A needs to interact with a contract on shard B, Nightshade uses asynchronous receipts to handle this (more details in the Logic Layer). [^14]

A major upgrade of this data layer came in August 2024, when Nightshade 2.0 introduced stateless validation. [^15] Previously, block producers had to maintain the state of every shard to verify transactions. Under the new design, a chunk producer maintains the state of its assigned shard and generates a state witness containing the information needed to verify a chunk, together with cryptographic proofs showing that the data matches the previously committed state. Other assigned chunk validators can use this witness to independently verify the transactions and check the resulting state changes, without storing the shard’s complete state themselves. Besides, a chunk must receive endorsements from more than two-thirds of its assigned validating stake before it can be included in a block. This reduces some storage requirements for validators, but the witnesses still have to be created and transmitted, and other nodes still maintain state. [^16]

Besides what’s been implemented, NEAR’s published roadmap describes further work on separating consensus from execution through SPICE, which is a new direction worth looking into since the development is moving fast. [^12]

### Logic Layer

NEAR’s logic layer is responsible for executing transactions and smart contracts and updating the blockchain’s state. Unlike Ethereum, which runs on the Ethereum Virtual Machine (EVM), NEAR runs smart contracts through a WebAssembly (WASM) runtime. Developers can write contracts in languages such as Rust or JavaScript, which are compiled into WASM for execution. [^17] Each contract execution consumes gas, and the resulting changes to account balances or contract storage are recorded in the blockchain’s state.

One important difference from Ethereum is how NEAR handles interactions between smart contracts. Instead of executing cross-contract calls synchronously, NEAR uses asynchronous receipts, meaning that a call to another contract is scheduled for execution later rather than completed immediately (it is similar to the asynchronous event loops used in many programming languages). For example, if a decentralized exchange contract calls a token contract to transfer assets, the transfer may execute in a later block and could fail after the original contract call has succeeded. This means developers must use callbacks to check the result and handle failures or refunds. This design allows contracts on different shards to execute independently and in parallel, though it also makes multi-contract transactions more complex because their operations are not automatically atomic. [^14]

![NEAR cross-shard transfer: a transaction on one shard creates receipts that execute in later chunks on another shard.](cross-shard-transfer.png)

*Cross-shard transfer schematic from [NEAR documentation](https://docs.near.org/protocol/data-flow/token-transfer-flow). Image reproduced without modification; [MIT license](near-docs-LICENSE-MIT.txt).*

### Application Layer

At the application layer, users interact with NEAR through wallets and decentralized applications (dApps), including decentralized exchanges (DEXs), games, and cross-chain services. These applications rely on NEAR’s underlying infrastructure to execute smart contracts and manage assets. Beyond applications built directly on NEAR, the ecosystem also provides tools for interacting with other blockchains. Two important components are NEAR Intents and Chain Signatures, which aim to simplify cross-chain transactions and account management. [^5] [^6]

NEAR Intents allows users to specify a desired outcome rather than worrying about how to execute each step of a transaction. For example, a user holding ETH on Ethereum may want to get SOL on Solana. The user can submit a request describing the assets they want to exchange. Independent service providers, called solvers, compete to fulfill the request by finding execution routes and providing liquidity. Through NEAR Intents, the user does not need to manually execute the intermediate steps. This simplifies cross-chain trading but introduces risks because it involves bridges, solver liquidity, and external networks. [^5]

Chain Signatures addresses a different aspect of the cross-chain problem. It uses multiparty computation (MPC) so that a NEAR account or application can help authorize transactions on supported external networks without requiring users to manage a separate private key for each network. In other words, Chain Signatures allows a NEAR account to control newly derived addresses on supported external blockchains, such as Ethereum, through an MPC network that collectively generates transaction signatures. However, it cannot control arbitrary existing wallet addresses, since those addresses are associated with different private keys that the MPC network does not possess. Instead of one party holding the complete signing key, the signing process is distributed among MPC participants. However, this introduces a separate security dependency because the MPC network has its own operators and signing thresholds, which are independent of NEAR’s layer-1 consensus. [^6]

## 3. Tokenomics: Supply, Allocation, and Incentives

### 3.1 Supply and Initial Distribution

NEAR created **1 billion tokens** at genesis in April 2020. The initial allocation was as follows. [^18]

| Allocation | Share of genesis supply |
| --- | ---: |
| Early backers | 23.7% |
| Core contributors | 14.0% |
| Community grants and programs | 17.2% |
| Community sale | 12.0% |
| Early ecosystem development | 11.7% |
| Operations grants | 11.4% |
| NEAR Foundation endowment | 10.0% |
| **Total** | **100.0%** |

Most genesis tokens were subject to lockup schedules, which restrict recipients from transferring or selling their allocated tokens. Core contributors had a four-year lockup with a 12-month cliff, meaning no tokens could be transferred during the first year, approximately 25% became transferable after 12 months, and the remainder was released gradually over the following three years. Early backers had lockups ranging from 12 to 36 months, while community and operations grants followed release schedules extending up to 60 months. Therefore, NEAR’s genesis distribution was fully unlocked by October 2025. [^18]

By October 13, 2026, NEAR had a total supply of approximately 1.309 billion tokens, with a market price near $5 and market capitalization around $6.5 billion. [^19] Unlike Bitcoin, NEAR has no fixed maximum supply. With the original lockup schedules completed, future supply growth is primarily determined by ongoing token issuance and transaction-fee burning rather than the release of genesis tokens. [^20]

### 3.2 New Issuance and Staking Incentives

NEAR uses Thresholded Proof of Stake, where validators stake NEAR to participate in block production and validation. Validator rewards are funded through newly issued tokens. NEAR originally had a maximum annual issuance rate of 5%, which was reduced to 2.5% in late 2025. [^21] Among newly issued tokens, 90% is distributed to staking participants while the remaining 10% goes to the protocol treasury. [^20] [^22] Based on the October 2026 total supply of 1.309 billion NEAR, the 2.5% annual ceiling represents approximately 32.7 million new NEAR per year. This issuance incentivizes network security but also dilutes holders who do not stake.

To offset new issuance, NEAR burns transaction fees, permanently removing tokens from circulation. Users pay gas fees in NEAR for transfers and smart contract execution. Under the original fee model, basic transaction fees are fully burned, while gas consumed by smart contract function execution is split: 70% is burned while 30% is credited to the contract account as a reward. Therefore, NEAR’s net supply growth depends on the difference between newly issued tokens and tokens burned through transactions. [^23]

In July 2026, NEAR governance approved HSP-027, a proposal to remove the 30% developer reward and burn 100% of execution gas fees instead. [^24] The change has been implemented in the codebase but has not yet been activated on mainnet at the time of writing. [^7] This change will increase the proportion of fees burned and decrease the net supply. A further reduction in annual issuance toward 1.6% was also under discussion. [^22] Both measures aim to reduce token inflation, although lower issuance would also reduce the rewards available to validators.

### 3.3 How the Token Is Used

NEAR serves several functions in the network. Users pay gas fees in NEAR when transferring assets or executing smart contracts, while validators and delegators stake NEAR to participate in network security and earn rewards. [^20]

NEAR also uses storage staking, meaning that there is a cost that developers need to “pay” for occupying shared state in the network — accounts and applications need to maintain a minimum NEAR balance proportional to the data they store on the blockchain. The current storage rate is 1 NEAR per 100 KB, meaning that a smart contract storing 100 KB of data must reserve roughly 1 NEAR in addition to other storage required for account and contract code. This amount remains in the contract account (effectively locked) but cannot be transferred or spent while the data is stored. Unlike transaction fees, these tokens are not spent or burned; once the data is deleted, the corresponding NEAR tokens will become available again. [^25]

NEAR is also used for governance through House of Stake, where holders can lock NEAR to receive non-transferable veNEAR voting power. This voting power can be used directly or delegated to representatives to participate in governance decisions. [^26]

## 4. Value Accrual and Revenue Flows

NEAR captures economic value through two main mechanisms: transaction-fee burning on its layer-1 blockchain and token buybacks funded by NEAR Intents. These mechanisms work differently. Burning permanently reduces token supply, while buybacks create demand for existing tokens without destroying them. [^23] [^27]

| Mechanism | Funding source | Effect on NEAR |
| --- | --- | --- |
| L1 fee burning | Transaction gas fees | Permanently removes tokens from supply. |
| Intents buybacks | Captured protocol revenue from cross-chain swaps | Buys existing tokens; holding them does not reduce total supply. |

### 4.1 Layer-1 Transaction Fees

Users pay gas fees in NEAR when transferring assets or executing smart contracts. As mentioned in Section 3.2, most of these fees (70%) are burned, partially offsetting the new tokens issued as staking rewards. However, NEAR’s low transaction costs limit fee-based value accrual to the NEAR token, as relatively little economic value is captured through burned gas fees compared with substantial on-chain activity. As of October 14, 2026, DefiLlama reported approximately $194,000 in L1 gas fees over the preceding 30 days. [^28] At around $5 per NEAR, this is equivalent to approximately 38,800 tokens in total fees, compared with roughly 2.69 million NEAR in potential issuance over the same period. Even if all gas fees were burned, they would offset only about 1.4% of new issuance. Therefore, NEAR’s current L1 activity generates insufficient fee revenue to significantly reduce token inflation.

### 4.2 NEAR Intents Revenue and Token Buybacks

NEAR Intents, which is at the application layer, generates revenue from cross-chain swaps through protocol fees and fees shared with distribution partners. According to DefiLlama, NEAR Intents processed approximately $4.81 billion in swap volume over the 30 days ending in mid-October 2026, generating $8.18 million in total fees. Of this amount, approximately $2.28 million (28%) was captured by NEAR as protocol revenue. [^27]

In February 2026, NEAR introduced a buyback program that uses revenue from Intents to purchase NEAR tokens on the open market, creating indirect demand for the token. [^27] The reported $2.28 million in 30-day protocol revenue was equivalent to approximately 17% of the estimated value of NEAR issued over the same period. Unlike transaction-fee burning, repurchased NEAR tokens are held rather than destroyed, so buybacks do not reduce the total token supply. [^27]

### 4.3 Interpreting NEAR’s Value

#### Labor and Network Security

Similar to Ethereum, NEAR uses a proof-of-stake mechanism where validators stake NEAR tokens to contribute to the network. These validators run nodes, verify transactions and state changes, and participate in consensus to prevent double spending and maintain a reliable and decentralized ledger. They are compensated mainly through newly issued NEAR. [^20] However, these rewards do not directly measure the economic value they create, since issuance also increases the total supply and dilutes the value of existing tokens as well.

#### Monetary Supply and Revenue

NEAR’s monetary value is influenced by the balance between token issuance and demand. New issuance increases total supply, while gas-fee burning removes tokens permanently. Revenue generated by Intents can create indirect demand as NEAR buys back tokens from the open market, although it does not reduce the total supply. [^23] [^27] As discussed in Sections 4.1 and 4.2, current fee burning remains very small relative to issuance, while Intents provides a large source of revenue-backed token demand. Overall, NEAR’s economic sustainability depends on whether growing activity on the network can generate enough fees and buyback demand compared to newly issued tokens. Also, it is worth keeping an eye on discussions about further reducing the annual issuance rate and how this will change the supply of and demand for the NEAR token.

#### Utility and Subjective Value

NEAR has several practical uses, including paying gas fees, storage staking, and validator staking. [^20] [^25] However, its market value also depends on how people perceive its usefulness and future potential. For example, NEAR Intents makes trading across chains so much easier, and users don’t even need to hold NEAR. [^5] Besides, as NEAR positions itself toward “User-Owned AI” and AI applications, people may value NEAR based on these expectations rather than focusing on what’s been shipped.

#### Power and Governance

NEAR’s economic policies are influenced by the distribution of governance power. Through House of Stake, token holders can lock NEAR to obtain veNEAR voting power, with longer lock periods granting greater influence. [^26] However, the concern is that the current governance is too concentrated. As of October 2026, the ten largest wallets controlled approximately 81% of veNEAR voting power, and just five delegates collectively held enough votes to form a simple majority. [^29] This concentration has economic consequences. For example, in July 2026, House of Stake approved HSP-027, a proposal to eliminate the 30% developer gas rebate and redirect those fees toward token burning once implemented. [^24] This shifts the economic benefit from smart contract developers toward reducing token inflation. Similar to Bitcoin and Ethereum, governance votes alone cannot change NEAR’s protocol without validators adopting the upgrade. [^24] [^7]

## 5. Decentralization and Security

### 5.1 Decentralization

Beyond the decentralized design of NEAR Protocol, there are two main concerns — whether validators and voting power are sufficiently decentralized. As mentioned in Section 4.3, governance is currently highly concentrated, with the ten largest wallets controlling approximately 81% of veNEAR voting power. [^29] In terms of the validators, the situation is better but still concerning: as of October 13, 2026, NEAR had 409 active validators with the nine largest validator pools controlling 35.53% of the total staked NEAR. [^30] Since NEAR requires more than two-thirds of the relevant stake to finalize blocks, the coordination of these top nine validator pools could cause a liveness issue for the chain. [^11] More details on why this happens will be discussed in Section 6.

### 5.2 Security Incident

An exploit disclosed on October 1, 2026, involving HOT Omni Bridge and NEAR Intents resulted in unauthorized withdrawals totaling approximately $3.8 million. The vulnerability was in the refund process of NEAR Intents (which is at the application layer). This bug was triggered when a deposit was credited through an Intents smart contract, but a later operation failed and the underlying assets were refunded without reversing the earlier credit. Because NEAR processes cross-contract calls asynchronously, the failure did not automatically roll back the successful earlier operation, allowing the attacker to withdraw assets against an improperly retained balance. [^31] The incident did not compromise NEAR’s layer-1 consensus, and the Intents team reported that all stolen funds were returned by October 2. [^32] However, it demonstrated how failures in cross-contract execution and bridge integration can expose user funds even when the underlying blockchain remains secure.

## 6. Personal Assessment

Overall, I’m quite optimistic. NEAR goes after problems at the protocol layer instead of patching them with apps on top, and it puts usability first, which is what actually drives adoption. The team also ships fast. Version 2.13 went live in July with dynamic resharding and ML-DSA signing, [^8] and the focus on AI agents fits where the industry is heading.

It is interesting to see that validator concentration occurs on NEAR, although the protocol uses Thresholded Proof of Stake to mitigate it. Since it’s PoS, the hardware bar isn’t that high: chunk validators are recommended to have 16 GB of RAM and a 2 TB NVMe drive. [^33] Still, most people delegate to a handful of well-known operators, and many operators rent cloud machines instead of buying hardware. Google Cloud itself notes that some NEAR validators run on its platform, [^1] and the top 11 validators together hold more than a third of the stake. [^30] Memory and storage prices climbing in the AI boom will only push more operators toward renting from hyperscalers.

On inflation, I'm less worried about it than about governance. Maximum issuance was cut from 5% to 2.5% in the 2.9.0 upgrade, although some validators were unhappy with how the change was introduced. [^21] [^34] Around 44%–47% of NEAR's total supply is staked with validators, meaning a large portion isn't immediately available for trading. Storage staking ties up some additional tokens, but I couldn't find a reliable figure for that. Staking doesn't eliminate inflation or dilution, and those tokens can eventually be withdrawn. Still, the amount of NEAR readily available to trade is smaller than the total supply might suggest. What concerns me more is how concentrated governance power is, especially when it comes to decisions about future token issuance.

As for the weakest link, the protocol itself looks well covered. ML-DSA is live on mainnet, and nearcore sits in a HackenProof program paying up to $1 million for critical bugs. [^9] [^35] Consensus keys aren’t post-quantum yet, and the roadmap targets 2027. [^9] My guess is the weak point is third-party dependencies like wallets, SDKs, and cross-chain integrations. The protocol bounty on HackenProof only covers nearcore, and the Intents SDK runs in a separate program with a much lower cap. [^35] [^36] Keeping things easy to use while limiting exposure to code NEAR doesn’t control is the hard balance to get right.

*Cover artwork: [NEAR documentation](https://github.com/near/docs/blob/00c5e33370fe67c4786329c03b1df8009de4a5e5/assets/docs/welcome-pages/1.near-protocol.webp), used under the [MIT license](near-docs-LICENSE-MIT.txt).*

## References

[^1]: Google Cloud. [NEAR: Growing Web3 Adoption Through Usability](https://cloud.google.com/blog/topics/startups/near-building-useable-web3-infrastructure-on-google-cloud). March 20, 2023. Accessed October 15, 2026.
[^2]: NEAR. [The History of NEAR Protocol](https://www.near.org/roadmap-history). Accessed October 15, 2026.
[^3]: NEAR Docs. [Account Model](https://docs.near.org/protocol/accounts-contracts/account-model). Accessed October 15, 2026.
[^4]: NEAR Docs. [Access Keys](https://docs.near.org/protocol/accounts-contracts/access-keys). Accessed October 15, 2026.
[^5]: NEAR Docs. [NEAR Intents: Overview](https://docs.near.org/chain-abstraction/intents/overview). Accessed October 15, 2026.
[^6]: NEAR Docs. [Chain Signatures](https://docs.near.org/chain-abstraction/chain-signatures). Accessed October 15, 2026.
[^7]: NEAR / nearcore. [Release Notes](https://github.com/near/nearcore/releases). Consulted for versions 2.13 and 2.14. The October 14, 2026 release 2.14.0-rc.4 is marked as a testnet pre-release; 2.14.0-rc.1 includes removal of the developer gas reward. Accessed October 15, 2026.
[^8]: NEAR, via PR Newswire. [NEAR Protocol Brings Quantum-Safe Signing to Mainnet](https://www.prnewswire.co.uk/news-releases/near-protocol-brings-quantum-safe-signing-to-mainnet-302829647.html). July 20, 2026. Accessed October 15, 2026.
[^9]: NEAR. [Quantum-Safe NEAR: The Roadmap to Post-Quantum Security](https://near.org/blog/near-quantum-safe-roadmap). August 24, 2026. Accessed October 15, 2026.
[^10]: NEAR Docs. [Validators](https://docs.near.org/protocol/network/validators). Accessed October 15, 2026.
[^11]: NEAR Nomicon. [Consensus](https://nomicon.io/ChainSpec/Consensus). The approval threshold is defined using the relevant block-producing stake, not a simple count of validator accounts. Accessed October 15, 2026.
[^12]: NEAR. [SPICE: Separation of Consensus and Execution](https://www.near.org/blog/separation-of-consensus-and-execution). Accessed October 15, 2026.
[^13]: NEAR. [Introducing Dynamic Resharding: Automatic Scaling for NEAR Protocol](https://www.near.org/blog/introducing-dynamic-resharding). May 20, 2026. Accessed October 15, 2026.
[^14]: NEAR Docs. [Cross-Contract Calls](https://docs.near.org/smart-contracts/anatomy/crosscontract). Accessed October 15, 2026.
[^15]: NEAR. [Near One Shares Q3 NEAR Protocol Roadmap Update](https://pages.near.org/blog/near-one-shares-q3-near-protocol-roadmap-update/). September 3, 2024. Accessed October 15, 2026.
[^16]: NEAR Enhancement Proposals. [NEP-0509: Stateless Validation](https://github.com/near/NEPs/blob/master/neps/nep-0509.md). Accessed October 15, 2026.
[^17]: NEAR Docs. [What Is a Smart Contract?](https://docs.near.org/smart-contracts/what-is). Accessed October 15, 2026.
[^18]: NEAR. [NEAR Token Supply and Distribution](https://www.near.org/blog/near-token-supply-and-distribution). October 13, 2020; updated October 16, 2020. Historical allocation and release schedules, not a source for current issuance parameters. Accessed October 15, 2026.
[^19]: CoinMarketCap. [NEAR Protocol: Market Data](https://coinmarketcap.com/currencies/near-protocol/). Live data source. The report’s exact October 13, 2026 supply, price, and capitalization snapshot was retained from the author’s draft and was not independently reproduced. Accessed October 15, 2026.
[^20]: NEAR Docs. [Tokens](https://docs.near.org/protocol/network/tokens). Used for token functions and economic mechanisms. Version-specific monetary-policy changes are documented separately in the release notes and governance proposals. Accessed October 15, 2026.
[^21]: NEAR / nearcore. [Release 2.9.0](https://github.com/near/nearcore/releases/tag/2.9.0). 2025. Documents the reduction of the maximum annual inflation rate from 5% to 2.5%. Accessed October 15, 2026.
[^22]: NEAR Forum. [HSP-XXX: Establish a 24-Month Issuance Ramp to a 1.6% Target Rate of NEAR Token Emissions](https://gov.near.org/t/hsp-xxx-establish-a-24-month-issuance-ramp-to-a-1-6-target-rate-of-near-token-emissions/42644). October 7, 2026. Draft proposal, not an activated issuance rule. Accessed October 15, 2026.
[^23]: NEAR Docs. [Gas (Execution Fees)](https://docs.near.org/protocol/transactions/gas). The 30% contract reward applies to eligible contract-execution gas; it should not be assumed to apply uniformly to every component of every transaction fee. Accessed October 15, 2026.
[^24]: NEAR House of Stake. [HSP-027: Remove the NEAR Developer Gas Rebate](https://gov.near.org/t/hsp-027-remove-the-near-developer-gas-rebate/42213). Proposal published June 15, 2026; the official July 6 update records ratification on July 3, 2026. Ratification is distinct from mainnet activation. Accessed October 15, 2026.
[^25]: NEAR Docs. [Storage Staking](https://docs.near.org/protocol/storage/storage-staking). Accessed October 15, 2026.
[^26]: NEAR House of Stake. [House of Stake](https://houseofstake.org/home). Accessed October 15, 2026.
[^27]: DefiLlama. [NEAR Intents: TVL, Fees, Revenue, Volume, and Methodology](https://defillama.com/protocol/near-intents). Distinguishes gross swap fees from NEAR’s captured revenue and describes buybacks beginning February 23, 2026. Rolling dashboard values change; the draft’s exact mid-October 30-day figures were not independently reproduced. Accessed October 15, 2026.
[^28]: DefiLlama. [NEAR: Chain Dashboard](https://defillama.com/chain/near). Live dashboard. The exact October 14, 2026, 30-day L1 fee snapshot in Section 4.1 was retained from the author’s draft and was not independently reproduced. Accessed October 15, 2026.
[^29]: NEAR House of Stake. [Governance Statistics](https://stats.houseofstake.org/). The indexed dashboard displayed the 81% top-ten voting-power figure and five delegates for a majority. A fresh, timestamped on-chain snapshot was not independently reconstructed. Accessed October 15, 2026.
[^30]: NearBlocks. [NEAR Validators](https://nearblocks.io/validators). Validator-data source. The draft’s exact October 13 count of 409 validators and 35.53% top-nine stake share could not be independently reproduced from the accessible page. The separate top-eleven statement also needs a dated snapshot and consistent measurement. Accessed October 15, 2026.
[^31]: CertiK. [HOT Bridge / NEAR Intents](https://www.certik.com/blog/hot-bridge-near-intents). October 8, 2026. Technical incident analysis of HOT Omni Bridge’s integration with NEAR Intents. The analysis includes activity preceding October 1; the event’s disclosure date and first exploit transaction should not be conflated. Accessed October 15, 2026.
[^32]: Unchained. [NEAR Intents Says Exploited $3.8 Million Is Back, Closes Its Hack Investigation](https://unchainedcrypto.com/near-intents-says-exploited-3-8-million-is-back-closes-its-hack-investigation/). October 5, 2026. Reports the team’s statement that funds were recovered by October 2. Accessed October 15, 2026.
[^33]: NEAR Nodes. [Validator Hardware Requirements](https://near-nodes.io/validator/hardware-validator). Requirements differ between chunk validators and block/chunk producers. Accessed October 15, 2026.
[^34]: NEAR House of Stake. [HSP-012: Two-Phase Model for Consensus Protocol Upgrades](https://gov.near.org/t/hsp-012-two-phase-model-for-consensus-protocol-upgrades/41709). October 22, 2025. Used for discussion of concerns about the upgrade process, not as evidence that every proposed procedural change was adopted. Accessed October 15, 2026.
[^35]: HackenProof. [NEAR Protocol Bug Bounty Program](https://hackenproof.com/programs/near-protocol/). Program scope and maximum reward; a bounty does not establish that the covered code is free of vulnerabilities. Accessed October 15, 2026.
[^36]: HackenProof. [NEAR Intents SDK Bug Bounty Program](https://hackenproof.com/programs/near-intents-sdk/). Accessed October 15, 2026.
