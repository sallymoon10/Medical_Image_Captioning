from utils import pyrootutils

root = pyrootutils.setup_root(
    search_from=__file__,
    indicator=["README.md"],
    pythonpath=True,
    dotenv=True,
)

import pytorch_lightning as pl
from omegaconf import DictConfig
from pytorch_lightning import Callback, LightningDataModule, LightningModule, Trainer
from pytorch_lightning.loggers import LightningLoggerBase

from utils import pylogger, utils
from typing import List, Optional, Tuple
import hydra

log = pylogger.get_pylogger(__name__)


@utils.task_wrapper
def train(cfg: DictConfig) -> Tuple[dict, dict]:
    """
    Training model with hydra and pytorch lightening wrapper (https://github.com/ashleve/lightning-hydra-template) 
    - Sets up experiment based on configs and command overrides
    """
    if cfg.get("seed"):
        pl.seed_everything(cfg.seed, workers=True)
    
    log.info(f"Instantiating datamodule <{cfg.datamodule._target_}>")
    datamodule: LightningDataModule = hydra.utils.instantiate(cfg.datamodule)

    add_configs_from_datamodule(cfg = cfg, datamodule=datamodule)

    log.info(f"Instantiating model <{cfg.model._target_}>")
    model: LightningModule = hydra.utils.instantiate(cfg.model)

    log.info("Instantiating callbacks...")
    callbacks: List[Callback] = utils.instantiate_callbacks(cfg.get("callbacks"))

    log.info("Instantiating loggers...")
    logger: List[LightningLoggerBase] = utils.instantiate_loggers(cfg.get("logger"))

    log.info(f"Instantiating trainer <{cfg.trainer._target_}>")
    trainer: Trainer = hydra.utils.instantiate(cfg.trainer, callbacks=callbacks, logger=logger)

    object_dict = {
        "cfg": cfg,
        "datamodule": datamodule,
        "model": model,
        "callbacks": callbacks,
        "logger": logger,
        "trainer": trainer,
    }

    if logger:
        log.info("Logging hyperparameters!")
        utils.log_hyperparameters(object_dict)

    if cfg.get("train"):
        log.info("Starting training!")
        trainer.fit(model=model, datamodule=datamodule, ckpt_path=cfg.get("ckpt_path"))

    train_metrics = trainer.callback_metrics

    if cfg.get("test"):
        log.info("Starting testing!")
        ckpt_path = trainer.checkpoint_callback.best_model_path
        if ckpt_path == "":
            log.warning("Best ckpt not found! Using current weights for testing...")
            ckpt_path = None
        trainer.test(model=model, datamodule=datamodule, ckpt_path=ckpt_path)
        log.info(f"Best ckpt path: {ckpt_path}")

    test_metrics = trainer.callback_metrics
    metric_dict = {**train_metrics, **test_metrics}

    return metric_dict, object_dict

def add_configs_from_datamodule(cfg: DictConfig, datamodule):
    cfg.model.data_dir = datamodule.data_dir

@hydra.main(version_base="1.3", config_path="../configs", config_name="train.yaml")
def main(cfg: DictConfig) -> Optional[float]:
    metric_dict, _ = train(cfg)

    metric_value = utils.get_metric_value(
        metric_dict=metric_dict, metric_name=cfg.get("optimized_metric")
    )
    return metric_value


if __name__ == "__main__":
    main()

    '''
    poetry run python train.py datamodule='flickr.yaml'

    poetry run python train.py datamodule='medicat.yaml'
    '''
